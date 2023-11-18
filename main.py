from dotenv import load_dotenv

import database.db as db
import services.analysis_service as analysis_service
import services.setup_service as setup_service
from classes.analysis_data import AnalysisData
from config import config
from helpers.print_helpers import print_block_title

load_dotenv()

if __name__ == "__main__":
    print_block_title("Welcome to the Connection Tester!", "MAGENTA")

    # Setup AnalysisData
    config['analysis_data'] = AnalysisData()

    # Initialize things
    db.setup_db()
    setup_service.prompt_for_settings()
    analysis_service.display_info()
    analysis_service.run_analysis()
