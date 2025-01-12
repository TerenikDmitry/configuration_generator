import json
from itertools import product
from typing import Dict, List


class Classifier:

    def __init__(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        self.groups = config_data['groups']
        self.filters = config_data['filters']

        self.code_form_all = []

    def _format_strategy(self, strategy_dict: Dict[str, str], _code_form_all: List[List[str]]) -> str:
        """
        Форматує результат за схемою:
           група1/група2/...
           група = фічі1-фіча2-...
        Приклад:
            "ПН/РЦ-ПР/СП-БМ-ПТ"
        """
        groups_formated = []
        for _code_form_all in self.code_form_all:
            groups_formated.append(
                '-'.join(strategy_dict[form_key] for form_key in _code_form_all if strategy_dict[form_key])
            )
        return '/'.join(groups_formated)

    def _passes_filters(self, strategy_dict) -> bool:
        """
        Перевіряє, чи відповідає strategy_dict усім правилам з filters.
        strategy_dict вигляду:
            {
              "Можливість переривання зв’ язку": "ПН",
              "Резервування системи": "БР",
              "Метод резервування": "ПР",
              ...
            }
        """
        for rule in self.filters:
            # Кожне rule має:
            #   "if": ["X==AAA", "Y==BBB", ...] (Але тут, як правило, один рядок)
            #   "then": ["Z!=CCC", ...]
            # Якщо всі "if" спрацювали, то всі "then" мають виконуватися.

            # 1) Перевіряємо умови if
            if_conditions = rule["if"]
            all_if_matched = True
            for cond in if_conditions:
                # Наприклад, "Резервування системи==БР"
                # Розпарсимо (назва_фічі, операція, значення)
                if "==" in cond:
                    feat_name, check_value = cond.split("==")
                    operation = "=="

                if "!=" in cond:
                    feat_name, check_value = cond.split("==")
                    operation = "=!"

                check_value = check_value.strip()
                feat_name = feat_name.strip()

                if feat_name not in strategy_dict:
                    # Якщо раптом у нас немає такої фічі (теоретично не повинно бути), пропускаємо
                    all_if_matched = False
                    break

                current_val = strategy_dict[feat_name]
                if operation == "==":
                    if current_val != check_value:
                        all_if_matched = False
                        break

                if operation == "!=":
                    if current_val == check_value:
                        all_if_matched = False
                        break

            # 2) Якщо всі if-умови виконані, перевіряємо then
            if all_if_matched:
                for then_cond in rule["then"]:
                    # Приклад: "Метод резервування!=ПР"
                    if "==" in then_cond:
                        feat_name, required_val = then_cond.split("==")
                        feat_name = feat_name.strip()
                        required_val = required_val.strip()
                        # Якщо rule каже "...==...", тоді strategy_dict[feat_name] має дорівнювати required_val
                        if strategy_dict.get(feat_name, None) != required_val:
                            return False

                    if "!=" in then_cond:
                        feat_name, forbidden_val = then_cond.split("!=")
                        feat_name = feat_name.strip()
                        forbidden_val = forbidden_val.strip()
                        # Якщо rule каже "...!=...", тоді strategy_dict[feat_name] НЕ має бути forbidden_val
                        if strategy_dict.get(feat_name, None) == forbidden_val:
                            return False

                    if "(None)" in then_cond:
                        feat_name, required_val = then_cond.split("(None)")
                        feat_name = feat_name.strip()
                        required_val = required_val.strip()
                        # Якщо rule каже "...==...", тоді strategy_dict[feat_name] має дорівнювати required_val
                        strategy_dict[feat_name] = None
                        return True

        return True

    def calculate_combinations(self) -> List[str]:

        # Додатковий лист для форматування
        self.code_form_all = []

        group_combinations = []
        for group_id in sorted(self.groups.keys(), key=int):
            group_features = self.groups[group_id]["features"]
            # зібрати всі features по групі
            group_feat_options = []
            code_form = []

            for feat_id in sorted(group_features.keys(), key=int):
                feat_name = group_features[feat_id]["name"]
                code_form.append(feat_name)
                options = group_features[feat_id]["options"]
                # зберігаємо (ім'я фічі, code опції) для кожного варіанта
                group_feat_options.append([(feat_name, opt["code"]) for opt in options])

            self.code_form_all.append(code_form)

            # Зробимо добуток усередині групи
            group_combinations.append(list(product(*group_feat_options)))

        # Зробимо тепер добуток group_features (тобто груп 1,2,3) між собою,
        # щоб зібрати всі можливі "стратегії".
        all_combinations = list(product(*group_combinations))

        # Для прикладу, кожен елемент all_combinations виглядатиме так:
        # (
        #   ((feat_name1_g1, code1_g1), ),  # група 1 (одна фіча, один code)
        #   ((feat_name1_g2, code1_g2), (feat_name2_g2, code2_g2)),  # група 2 (дві фічі)
        #   ((feat_name1_g3, code1_g3), (feat_name2_g3, code2_g3), (feat_name3_g3, code3_g3)) # група 3
        # )

        valid_strategies = []

        def combination_to_dict(combination):
            """Converts a single 'string' from product(...) into a dictionary {feature_name: code}."""
            result = {}
            for group_block in combination:
                for (fname, code) in group_block:
                    result[fname] = code
            return result

        for combo in all_combinations:
            strat_dict = combination_to_dict(combo)
            if self._passes_filters(strat_dict):
                valid_strategies.append(strat_dict)

        return list(dict.fromkeys([self._format_strategy(valid_strategy, self.code_form_all) for valid_strategy in valid_strategies]))


if __name__ == '__main__':
    classifier = Classifier('projects/project_example.json')
    valid_combinations = classifier.calculate_combinations()

    print("All possible deployment strategies (including filters):")
    for idx, valid_combination in enumerate(valid_combinations, start=1):
        print(f"{idx}. {valid_combination}")
