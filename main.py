from services.meta_service import print_env_variables
from database.db import setup_db
from services.analysis_service import start_new_analysis
from helpers.print_helpers import print_block_title

if __name__ == "__main__":
    print_block_title("Welcome to the Connection Tester!", "MAGENTA")
    setup_db()
    print_env_variables()
    start_new_analysis()
