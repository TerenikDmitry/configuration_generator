import json
from itertools import product
from typing import List


class ClassifierNew:

    def __init__(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        self.features = config_data['features']
        self.constraints = config_data['constraints']

        self.model = [feature['name'] for feature in self.features]

    def calculate_combinations(self) -> List[str]:
        # Створення словника ознак з їхніми доменами
        features = {feature['name']: feature['domain'] for feature in self.features}

        # Генерація всіх можливих комбінацій
        all_combinations = list(product(*features.values()))
        feature_names = list(features.keys())

        valid_configurations = set()

        for combination in all_combinations:
            config = dict(zip(feature_names, combination))
            is_valid = True

            for constraint in self.constraints:
                if constraint['rule_type'] == 'conditional':
                    # Перевірка умов
                    check_condition = True
                    for condition in constraint['conditions']:
                        condition_feature = condition['feature']
                        condition_value = condition['value']

                        if config[condition_feature] != condition_value:
                            check_condition = False
                            break

                    if not check_condition:
                        continue

                    for action in constraint['actions']:
                        action_feature = action['feature']
                        action_mode = action['mode']

                        if action_mode == 'block':
                            allowed_values = action['allowed_values']
                            if config[action_feature] not in allowed_values:
                                is_valid = False
                                break
                        elif action_mode == 'null':
                            config[action_feature] = 'None'

                    if not is_valid:
                        break

                elif constraint['rule_type'] == 'domain':
                    domain_feature = constraint['feature']
                    domain_allowed_values = constraint['allowed_values']
                    if config[domain_feature] not in domain_allowed_values:
                        is_valid = False
                        break

                else:
                    raise Exception(f'Unknown constraint type {constraint["rule_type"]}')

            if is_valid:
                valid_configurations.add('/'.join(config[_key] for _key in self.model))

        return list(valid_configurations)


if __name__ == '__main__':
    classifier_new = ClassifierNew('projects/project_example_new.json')
    valid_combinations = classifier_new.calculate_combinations()

    print("All possible deployment strategies (including filters):")
    for idx, valid_combination in enumerate(valid_combinations, start=1):
        print(f"{idx}. {valid_combination}")
