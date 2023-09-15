class AnalysisState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnalysisState, cls).__new__(cls)
            cls._instance.analysis_id = None
        return cls._instance
