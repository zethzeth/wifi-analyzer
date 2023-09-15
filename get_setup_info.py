import subprocess


def get_first_nameserver(domain):
    try:
        # Execute the dig command
        result = subprocess.check_output(
            ["dig", "+trace", domain], stderr=subprocess.STDOUT, text=True
        )

        # Parse the output to find the first nameserver
        for line in result.split("\n"):
            if "Received " in line:
                parts = line.split()
                if len(parts) > 4:
                    return parts[5]  # Return the IP address of the first nameserver
                    # return parts[5].split("#")[0]
        return None  # Return None if not found

    except subprocess.CalledProcessError:
        print("Error executing dig command.")
        return None


if __name__ == "__main__":
    domain = input("Enter the domain (e.g., google.com): ")
    nameserver = get_first_nameserver(domain)
    if nameserver:
        print(f"The first nameserver for {domain} is: {nameserver}")
    else:
        print(f"Couldn't determine the first nameserver for {domain}.")
