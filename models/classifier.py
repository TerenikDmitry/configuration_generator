import json
from itertools import product
from typing import List, Tuple, Dict


class ConfigurationGenerator:
    """
    A class for generating and validating configurations based on features and constraints.

    Attributes:
        features (List[dict]): List of features, each with a name, domain, and optional group.
        constraints (List[dict]): List of constraints, each defining rules for valid configurations.
        feature_sequence (List[str]): Ordered list of feature names, defining the sequence for configuration output.
    """

    def __init__(self, file_path: str):
        """
        Initialize the classifier by loading features and constraints from a JSON file.

        Args:
            file_path (str): Path to the JSON configuration file.
        """

        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        self.features = config_data['features']
        self.constraints = config_data['constraints']

        # Define the sequence of features for consistent configuration output
        self.feature_sequence = [feature['name'] for feature in self.features]

    def _format_configuration(self, config: Dict) -> str:
        """
        Format a configuration dictionary into a string representation based on feature sequence.

        Args:
            config (dict): A dictionary representing a configuration.

        Returns:
            str: A formatted string representing the configuration.
        """
        return '/'.join(config[_key] for _key in self.feature_sequence)

    def calculate_all_configurations(self) -> List[str]:
        """
        Generate all possible configurations without applying constraints.

        Returns:
            List[str]: A list of all possible configurations, formatted as strings.
        """

        feature_domains = [feature['domain'] for feature in self.features]
        all_combinations = list(product(*feature_domains))

        all_configurations = list()
        for combination in all_combinations:
            config = dict(zip(self.feature_sequence, combination))
            formatted_config = self._format_configuration(config)
            if formatted_config not in all_configurations:
                all_configurations.append(formatted_config)
        return all_configurations

    def calculate_valid_configurations(self) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        Generate all valid configurations by applying constraints and identify blocked configurations.

        Returns:
            Tuple[List[str], List[Tuple[str, str]]]:
                - A list of valid configurations, formatted as strings.
                - A list of tuples containing constraint IDs and corresponding blocked configurations.
        """

        # Create a dictionary of feature domains
        features = {feature['name']: feature['domain'] for feature in self.features}

        # Generate all possible combinations of feature values
        all_combinations = list(product(*features.values()))

        valid_configurations = list()
        blocked_configurations = list()

        for combination in all_combinations:
            config = dict(zip(self.feature_sequence, combination))
            is_valid = True

            constraint = dict()
            for constraint in self.constraints:
                if constraint['rule_type'] == 'conditional':
                    # Check conditions
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
                    # Check domain constraints
                    domain_feature = constraint['feature']
                    domain_allowed_values = constraint['allowed_values']
                    if config[domain_feature] not in domain_allowed_values:
                        is_valid = False
                        break

                else:
                    raise Exception(f'Unknown constraint type {constraint["rule_type"]}')

            formatted_config = self._format_configuration(config)

            if is_valid and formatted_config not in valid_configurations:
                valid_configurations.append(formatted_config)

            if not is_valid and constraint:
                blocked_configurations.append((constraint['id'], formatted_config))

        return valid_configurations, blocked_configurations
