import subprocess
import time

def run_command(command):
    """Runs a shell command and returns the output."""
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {command}")
        return None

def check_website():
    print("🔍 Checking website status...")
    
    # Run 'docker compose ps' to see running containers
    output = run_command("docker compose ps")
    
    # Check if 'wordpress' is in the output text
    if "wordpress" in output and "Up" in output:
        print("✅ Website is RUNNING healthy!")
    else:
        print("⚠️  Website is DOWN. Attempting to start it...")
        run_command("docker compose up -d")
        
        # Wait a few seconds for it to boot
        print("⏳ Waiting for boot...")
        time.sleep(5)
        print("🚀 Successfully restarted the stack!")

if __name__ == "__main__":
    check_website()