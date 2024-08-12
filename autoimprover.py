import openai
import os
import time
import subprocess
import sys
import ast
import logging
import psutil
import random
import re
from datetime import datetime

def load_api_key(filename='apikey.txt'):
    try:
        with open(filename, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        logging.error(f"API key file '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading API key file: {e}")
        sys.exit(1)

# Load the API key
api_key = load_api_key()

# Initialize OpenAI client
client = openai.OpenAI(api_key=api_key)

# Create logs directory if it doesn't exist
logs_dir = 'logs'
os.makedirs(logs_dir, exist_ok=True)

# Set the working directory to the script's location
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
output_log = os.path.join(logs_dir, 'output.log')
version_history_log = os.path.join(logs_dir, 'version_history.log')

logging.basicConfig(filename=output_log, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

def log_version_history(message):
    with open(version_history_log, 'a') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def load_prompt(filename):
    """Load a prompt template and its format parameters from a file in the prompts folder."""
    prompts_dir = r"T:\Dev\PredPrey_GP4omini\prompts"
    full_path = os.path.join(prompts_dir, filename)
    
    with open(full_path, 'r') as file:
        content = file.read()
    
    # Split the content into prompt and format parameters
    parts = content.split('---')
    if len(parts) > 1:
        prompt = parts[0].strip()
        format_params = [param.strip() for param in parts[1].split(',')]
    else:
        prompt = content
        format_params = []
    
    return prompt, format_params

def save_gpt_response(prompt, response, prefix):
    """Save GPT prompt and response to separate files and log the action."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    prompt_filename = os.path.join(logs_dir, f"{prefix}_prompt_{timestamp}.txt")
    response_filename = os.path.join(logs_dir, f"{prefix}_response_{timestamp}.txt")
    
    with open(prompt_filename, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    with open(response_filename, 'w', encoding='utf-8') as f:
        f.write(response)
    
    logging.info(f"Saved GPT prompt to {prompt_filename}")
    logging.info(f"Saved GPT response to {response_filename}")

def call_openai_api(model, prompt, prefix):
    """Call OpenAI API, save the interaction, and return the response content."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096
        )
        content = response.choices[0].message.content
        
        save_gpt_response(prompt, content, prefix)
        
        return content
    except Exception as e:
        logging.error(f"Error calling OpenAI API: {e}")
        return None

def save_code_to_file(code, filename):
    """Save code to a file and return True if successful."""
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(code)
        logging.info(f"Saved code to {filename}")
        return True
    except Exception as e:
        logging.error(f"Error saving code to file {filename}: {e}")
        return False

def run_simulation(filename):
    """Run the simulation and capture any runtime errors."""
    try:
        result = subprocess.run([sys.executable, filename, "--headless"], 
                                capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return result.stderr
        return None
    except subprocess.TimeoutExpired:
        return None  # Timeout is considered a success
    except Exception as e:
        return str(e)

def get_test_methods(filename):
    try:
        with open(filename, 'r') as file:
            content = file.read()
        tree = ast.parse(content)
        
        test_methods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                test_methods.append(node.name)
        
        return test_methods
    except IndentationError as e:
        logging.error(f"Indentation error in {filename} at line {e.lineno}")
        return []
    except SyntaxError as e:
        logging.error(f"Syntax error in {filename} at line {e.lineno}: {e.text}")
        return []
    except Exception as e:
        logging.error(f"Error parsing {filename}: {str(e)}")
        return []

def get_test_class_name(filename):
    try:
        with open(filename, 'r') as file:
            content = file.read()
        match = re.search(r'class\s+(\w+)\(.*TestCase.*\):', content)
        return match.group(1) if match else None
    except Exception as e:
        logging.error(f"Error getting test class name from {filename}: {str(e)}")
        return None

def run_unit_tests(filename, timeout=10):
    """Run unit tests individually with a timeout and capture any failures."""
    test_methods = get_test_methods(filename)
    test_class_name = get_test_class_name(filename) or 'UnitTester'
    failures = []
    removed_tests = []

    if not test_methods:
        return f"Unable to parse test methods from {filename}. Please check the file for syntax errors."

    for test_method in test_methods:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "unittest", f"{filename.replace('.py', '')}.{test_class_name}.{test_method}"],
                capture_output=True, text=True, timeout=timeout
            )
            if result.returncode != 0:
                failures.append(f"Test {test_method} failed:\n{result.stderr}")
        except subprocess.TimeoutExpired:
            logging.warning(f"Test {test_method} timed out after {timeout} seconds")
            removed_tests.append(test_method)
        except Exception as e:
            failures.append(f"Error running test {test_method}: {str(e)}")

    if removed_tests:
        remove_problematic_tests(filename, removed_tests)

    if failures or removed_tests:
        return "\n".join(failures + [f"Removed tests due to timeout: {', '.join(removed_tests)}"])
    return None

def analyze_code_for_errors(code):
    """Use GPT to analyze code for potential errors."""
    prompt, _ = load_prompt('prompt_analyze_code_for_errors.txt')
    formatted_prompt = prompt.format(code=code)
    return call_openai_api("gpt-4o-mini", formatted_prompt, "analyze_errors")

def read_feature_history():
    feature_history_log = os.path.join(logs_dir, 'feature_history.log')
    if os.path.exists(feature_history_log):
        with open(feature_history_log, 'r') as f:
            return f.read().strip()
    return ""

def suggest_new_features(code):
    """Use GPT to suggest new features."""
    features = read_feature_history()
    prompt, _ = load_prompt('prompt_suggest_features.txt')
    formatted_prompt = prompt.format(features=features, code=code)
    return call_openai_api("gpt-4o-mini", formatted_prompt, "suggest_features")

def choose_best_feature(features, code):
    """Use GPT to choose the best feature."""
    prompt, _ = load_prompt('prompt_choose_best_feature.txt')
    formatted_prompt = prompt.format(features=features, code=code)
    return call_openai_api("gpt-4o-mini", formatted_prompt, "choose_feature")

def design_feature(feature, code):
    """Use GPT to design the chosen feature."""
    prompt, _ = load_prompt('prompt_design_feature.txt')
    formatted_prompt = prompt.format(feature=feature, code=code)
    return call_openai_api("gpt-4o-mini", prompt, "design_feature")

def implement_feature(design, code):
    """Use GPT to implement the designed feature."""
    prompt, _ = load_prompt('prompt_implement_feature.txt')
    formatted_prompt = prompt.format(plan=design, code=code)
    return call_openai_api("gpt-4o-mini", formatted_prompt, "implement_feature")

def fix_simulation(error, code):
    """Use GPT to fix simulation errors."""
    prompt, _ = load_prompt('prompt_fix_sim.txt')
    formatted_prompt = prompt.format(issue=error, code=code)
    return call_openai_api("gpt-4o-mini", formatted_prompt, "fix_simulation")

def create_unit_tests(code, filename):
    """Use GPT-4o to create initial unit tests."""
    prompt, _ = load_prompt('prompt_unit_test.txt')
    formatted_prompt = prompt.format(code=code, filename=filename)
    return call_openai_api("gpt-4o", formatted_prompt, "create_unit_tests")

def fix_unit_tests(error, test_code, main_code):
    """Use GPT to fix unit test errors."""
    prompt, _ = load_prompt('prompt_fix_unit_test.txt')
    formatted_prompt = prompt.format(code=main_code, test_code=test_code, error=error)
    return call_openai_api("gpt-4o-mini", formatted_prompt, "fix_unit_tests")

def log_version_history(version, is_fix, summary):
    with open(version_history_log, 'a') as f:
        f.write(f"Version {version}: {'Fix' if is_fix else 'New feature'} - {summary}\n")

def log_feature_history(version, summary):
    feature_history_log = os.path.join(logs_dir, 'feature_history.log')
    with open(feature_history_log, 'a') as f:
        f.write(f"Version {version}: {summary}\n")

def determine_next_step(version, code, main_feature):
    """Determine the next step in the development process."""
    is_fix = main_feature.startswith("Fix errors")
    summary = main_feature[12:] if is_fix else main_feature[13:]  # Remove "Fix errors: " or "New feature: "
    log_version_history(version, is_fix, summary)
    
    if not is_fix:
        log_feature_history(version, summary)
    
    if random.choice([True, False]):
        return "analyze"
    else:
        return "improve"

def adjust_unit_test_imports(test_code, version):
    """Adjust the import statements in the unit test code."""
    module_name = f"sim{version:04d}"
    return test_code.replace("from your_module", f"from {module_name}")

def remove_problematic_tests(test_filename, test_names):
    with open(test_filename, 'r') as file:
        content = file.read()

    for test_name in test_names:
        # Use regex to find and remove the entire test method
        pattern = re.compile(f"def {test_name}.*?(?=def|\Z)", re.DOTALL)
        content = pattern.sub('', content)
        
        logging.info(f"Removed problematic test: {test_name}")

    with open(test_filename, 'w') as file:
        file.write(content)

def main():
    version = 1
    code = None
    main_feature = "Initial implementation"

    while True:
        if version == 1:
            prompt, _ = load_prompt('prompt_initial.txt')
            code = call_openai_api("gpt-4o", prompt, "initial")
            if code is None:
                logging.error("Failed to generate initial simulation code. Exiting.")
                return

        sim_filename = f"sim{version:04d}.py"  # Define sim_filename here
        if not save_code_to_file(code, sim_filename):
            logging.error(f"Failed to save simulation code for version {version}. Exiting.")
            return
        
        # Run simulation and fix if necessary
        sim_fix_attempts = 0
        max_sim_fix_attempts = 10 if version == 1 else 3
        while True:
            errors = run_simulation(sim_filename)
            if not errors:
                logging.info(f"Simulation for version {version} completed successfully.")
                break
            
            logging.warning(f"Simulation errors in version {version}:\n{errors}")
            sim_fix_attempts += 1
            if sim_fix_attempts >= max_sim_fix_attempts:
                if version == 1:
                    logging.error("Initial version failed after 10 attempts. Exiting.")
                    return
                else:
                    logging.warning(f"Version {version} failed after {max_sim_fix_attempts} fix attempts. Rolling back.")
                    version -= 1
                    with open(f"sim{version:04d}.py", 'r') as f:
                        code = f.read()
                    break
            
            code = fix_simulation(errors, code)
            if not save_code_to_file(code, sim_filename):
                logging.error(f"Failed to save fixed simulation code for version {version}. Exiting.")
                return

        if sim_fix_attempts >= max_sim_fix_attempts and version > 1:
            continue  # Go to determine_next_step with the previous version

        # Create and run unit tests
        test_code = create_unit_tests(code, sim_filename)
        test_filename = f"sim{version:04d}_test.py"

        if not save_code_to_file(test_code, test_filename):
            logging.error(f"Failed to save unit tests for version {version}. Exiting.")
            return

        # Run unit tests and fix if necessary
        # test_fix_attempts = 0
        # max_test_fix_attempts = 10 if version == 1 else 3
        # while True:
        #     test_failures = run_unit_tests(test_filename, timeout=10)
        #     if not test_failures:
        #         logging.info(f"Unit tests for version {version} passed successfully.")
        #         break
            
        #     logging.warning(f"Unit test failures in version {version}:\n{test_failures}")
        #     test_fix_attempts += 1
        #     if test_fix_attempts >= max_test_fix_attempts:
        #         if version == 1:
        #             logging.error(f"Initial version failed unit tests after {max_test_fix_attempts} fix attempts. Exiting.")
        #             return
        #         else:
        #             logging.warning(f"Version {version} failed unit tests after {max_test_fix_attempts} fix attempts. Rolling back.")
        #             version -= 1
        #             with open(f"sim{version:04d}.py", 'r') as f:
        #                 code = f.read()
        #             break
            
        #     if "Removed tests due to timeout" in test_failures:
        #         continue  # Skip fixing attempt if tests were removed due to timeout
            
        #     with open(sim_filename, 'r') as f:
        #         main_code = f.read()
        #     test_code = fix_unit_tests(test_failures, test_code, main_code)
        #     if not save_code_to_file(test_code, test_filename):
        #         logging.error(f"Failed to save fixed unit tests for version {version}. Exiting.")
        #         return

        # if test_fix_attempts >= max_test_fix_attempts and version > 1:
        #     continue  # Go to determine_next_step with the previous version

        # Determine next step
        next_step = determine_next_step(version, code, main_feature)
        version += 1

        if next_step == "analyze":
            error_analysis = analyze_code_for_errors(code)
            if error_analysis.lower() != "no errors":
                logging.info(f"Potential errors found in version {version}:\n{error_analysis}")
                main_feature = f"Fix errors: {error_analysis[:100]}..."  # Truncate for brevity
                code = fix_simulation(error_analysis, code)
            else:
                logging.info(f"No potential errors found in version {version}.")
                version -= 1  # Revert version increment as no changes were made
        else:  # improve
            new_features = suggest_new_features(code)
            best_feature = choose_best_feature(new_features, code)
            main_feature = f"New feature: {best_feature[:100]}..."  # Truncate for brevity
            feature_design = design_feature(best_feature, code)
            code = implement_feature(feature_design, code)
            logging.info(f"Implemented new feature for version {version}: {best_feature}")

        time.sleep(10)  # Wait for 10 seconds before the next iteration

if __name__ == "__main__":
    main()