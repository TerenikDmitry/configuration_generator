import json
from itertools import product
from typing import Dict, List


class ClassifierNew:

    def __init__(self, file_path: str):
        config_date = json.load(open(file_path))

        self.features = config_date['features']
        self.constraints = config_date['constraints']

    def calculate_combinations(self) -> List[str]:
        # Створення словника ознак з їхніми доменами
        features = {feature['name']: feature['domain'] for feature in self.features}

        # Генерація всіх можливих комбінацій
        all_combinations = list(product(*features.values()))
        feature_names = list(features.keys())

        valid_configurations = []

        for combination in all_combinations:
            config = dict(zip(feature_names, combination))
            is_valid = True

            for constraint in self.constraints:
                if constraint['rule_type'] == 'conditional':
                    condition_feature = constraint['condition']['feature']
                    condition_value = constraint['condition']['value']
                    if config[condition_feature] == condition_value:
                        for action in constraint['actions']:
                            action_feature = action['feature']
                            allowed_values = action['allowed_values']
                            if allowed_values:
                                if config[action_feature] not in allowed_values:
                                    is_valid = False
                                    break
                            else:
                                # allowed_values порожній список означає, що значення заборонені
                                is_valid = False
                                break
                # Можна додати обробку інших типів constraints тут
            if is_valid:
                valid_configurations.append(config)

        return valid_configurations


classifier_new = ClassifierNew('projects/project_example_new.json')

valid_combinations = classifier_new.calculate_combinations()

print("All possible deployment strategies (including filters):")
for valid_combination in valid_combinations:
    print(valid_combination)
