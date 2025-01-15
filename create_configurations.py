import argparse
from models.classifier import ConfigurationGenerator


def main(file_path: str):
    """
    Example usage:
    Load a JSON file containing features and constraints, generate all configurations,
    and identify valid and blocked configurations.

    Args:
        file_path (str): Path to the JSON configuration file.
    """
    configuration_generator = ConfigurationGenerator(file_path)

    # Generate all possible configurations
    all_combinations = configuration_generator.calculate_all_configurations()
    print(f"All possible configurations {len(all_combinations)}:")
    for idx, config in enumerate(all_combinations, start=1):
        print(f"{idx}. {config}")

    # Generate valid configurations and identify blocked configurations
    valid_combinations, blocked_combinations = configuration_generator.calculate_valid_configurations()

    print("\nValid configurations:")
    for idx, config in enumerate(valid_combinations, start=1):
        print(f"{idx}. {config}")

    print("\nBlocked configurations:")
    for idx, (constraint_id, config) in enumerate(blocked_combinations, start=1):
        print(f"{idx}. Blocked by ({constraint_id}): {config}")

    # Show constraint descriptions
    print("\nConstraints description:")
    for description in configuration_generator.list_constraints_descriptions():
        print(description)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the Configuration Generator with a JSON configuration file.")
    parser.add_argument('file_path', type=str, help="Path to the JSON configuration file.")
    args = parser.parse_args()

    main(args.file_path)
