"""
ADSE Configuration Management
Handles environment variables, Firebase initialization, and global settings
"""
import os
import logging
from typing import Dict, Any
from dataclasses import dataclass
from firebase_admin import credentials, initialize_app, firestore
from firebase_admin.exceptions import FirebaseError
import json

@dataclass
class ADSEConfig:
    """Central configuration dataclass with validation"""
    node_id: str
    firebase_project_id: str
    strategy_generation_interval: int = 300  # seconds
    backtest_window_days: int = 90
    min_strategy_confidence: float = 0.65
    max_concurrent_backtests: int = 5
    log_level: str = "INFO"
    
    def validate(self) -> bool:
        """Validate configuration parameters"""
        try:
            assert len(self.node_id) > 0, "Node ID cannot be empty"
            assert 60 <= self.strategy_generation_interval <= 3600, "Interval must be between 1min and 1hr"
            assert 0 <= self.min_strategy_confidence <= 1.0, "Confidence must be between 0 and 1"
            return True
        except AssertionError as e:
            logging.error(f"Configuration validation failed: {e}")
            return False

class ConfigManager:
    """Manages configuration and Firebase initialization"""
    
    def __init__(self):
        self.config = None
        self.firestore_client = None
        self._setup_logging()
        
    def _setup_logging(self):
        """Configure structured logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - [ADSE] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("ADSE Logging initialized")
    
    def load_config(self) -> ADSEConfig:
        """Load configuration from environment variables"""
        try:
            self.config = ADSEConfig(
                node_id=os.getenv('ADSE_NODE_ID', f"node_{os.urandom(4).hex()}"),
                firebase_project_id=os.getenv('FIREBASE_PROJECT_ID', ''),
                strategy_generation_interval=int(os.getenv('STRATEGY_INTERVAL', '300')),
                backtest_window_days=int(os.getenv('BACKTEST_WINDOW', '90')),
                min_strategy_confidence=float(os.getenv('MIN_CONFIDENCE', '0.65')),
                log_level=os.getenv('LOG_LEVEL', 'INFO')
            )
            
            if not self.config.validate():
                raise ValueError("Configuration validation failed")
            
            self.logger.info(f"Configuration loaded for node: {self.config.node_id}")
            return self.config
            
        except (ValueError, TypeError) as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
    
    def initialize_firebase(self) -> firestore.Client:
        """Initialize Firebase Admin SDK with error handling"""
        try:
            # Check for credentials in environment or file
            cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            else:
                # Try service account JSON from environment
                service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
                if service_account_json:
                    cred = credentials.Certificate(json.loads(service_account_json))
                else:
                    cred = credentials.ApplicationDefault()
            
            # Initialize Firebase
            app = initialize_app(cred, {
                'projectId': self.config.firebase_project_id
            })
            
            self.firestore_client = firestore.client(app)
            self.logger.info("Firebase Firestore initialized successfully")
            
            # Test connection
            test_doc = self.firestore_client.collection('system_health').document('connection_test')
            test_doc.set({
                'node_id': self.config.node_id,
                'timestamp