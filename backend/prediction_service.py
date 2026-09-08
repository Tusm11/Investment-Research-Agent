"""
Price Prediction Service
Loads XGBoost models and provides prediction functionality for both
consolidated (dashboard) and company-specific predictions.
"""
import pickle
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yfinance as yf
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PricePredictionService:
    def __init__(self):
        self.root = Path(__file__).resolve().parents[1]
        self.classifier_path = self.root / "xgb_classifier.pkl"
        self.regressor_path = self.root / "xgb_regressor.pkl"
        
        self.classifier = None
        self.regressor = None
        
        self._load_models()
    
    def _load_models(self):
        """Load XGBoost models from disk"""
        try:
            if self.classifier_path.exists():
                with open(self.classifier_path, 'rb') as f:
                    self.classifier = pickle.load(f)
                logger.info("XGBoost Classifier loaded successfully")
            else:
                logger.warning(f"Classifier not found at {self.classifier_path}")
            
            if self.regressor_path.exists():
                with open(self.regressor_path, 'rb') as f:
                    self.regressor = pickle.load(f)
                logger.info("XGBoost Regressor loaded successfully")
            else:
                logger.warning(f"Regressor not found at {self.regressor_path}")
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    def _calculate_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators from OHLCV data"""
        try:
            df = df.copy()
            
            # Price-based features
            df['returns'] = df['Close'].pct_change()
            df['log_returns'] = np.log(df['Close'] / df['Close'].shift(1))
            
            # Moving averages
            df['sma_5'] = df['Close'].rolling(window=5).mean()
            df['sma_10'] = df['Close'].rolling(window=10).mean()
            df['sma_20'] = df['Close'].rolling(window=20).mean()
            df['sma_50'] = df['Close'].rolling(window=50).mean()
            
            # Exponential moving averages
            df['ema_12'] = df['Close'].ewm(span=12).mean()
            df['ema_26'] = df['Close'].ewm(span=26).mean()
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_diff'] = df['macd'] - df['macd_signal']
            
            # RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            df['bb_middle'] = df['Close'].rolling(window=20).mean()
            bb_std = df['Close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            
            # Volume features
            df['volume_sma'] = df['Volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['Volume'] / df['volume_sma']
            
            # Volatility
            df['volatility'] = df['returns'].rolling(window=20).std()
            
            # Price momentum
            df['momentum'] = df['Close'] - df['Close'].shift(10)
            
            # Rate of change
            df['roc'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating features: {e}")
            return df
    
    def _prepare_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """Prepare feature vector for prediction"""
        try:
            # Expected features for the model (9 features based on error message)
            # Adjust this list to match your training features
            feature_cols = [
                'returns', 'sma_5', 'sma_20', 'rsi', 
                'macd', 'bb_width', 'volume_ratio', 
                'volatility', 'momentum'
            ]
            
            # Use the most recent row where every feature is a real value
            # (rolling windows produce leading NaNs; never impute with medians)
            valid = df[feature_cols].dropna()
            if valid.empty:
                logger.warning(f"No valid feature rows after NaN drop")
                return None
            latest = valid.iloc[-1]

            return latest.values.reshape(1, -1)
            
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return None
    
    def predict_single_company(self, ticker: str, current_price: float) -> Dict:
        """
        Predict price direction and target for a single company
        
        Returns:
            dict with predicted_price, expected_return, direction, confidence
        """
        try:
            # Fetch historical data
            stock = yf.Ticker(ticker)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            
            df = stock.history(start=start_date, end=end_date)
            # yfinance currently returns rows with NaN Close — drop them so the
            # latest feature row reflects a real trading day
            df = df.dropna(subset=["Close"])
            
            if df.empty or len(df) < 50:
                logger.warning(f"Insufficient data for {ticker}")
                return {
                    "current_price": current_price,
                    "predicted_price": None,
                    "expected_return": None,
                    "direction": "INSUFFICIENT DATA"
                }
            
            # Calculate features
            df = self._calculate_technical_features(df)
            
            # Prepare feature vector
            features = self._prepare_features(df)
            
            if features is None:
                return {
                    "current_price": current_price,
                    "predicted_price": None,
                    "expected_return": None,
                    "direction": "ERROR"
                }
            
            # Predictions
            direction = "NEUTRAL"
            predicted_price = current_price
            
            # Classifier prediction (UP/DOWN)
            if self.classifier is not None:
                pred_class = self.classifier.predict(features)[0]
                direction = "UP" if pred_class == 1 else "DOWN"
            
            # Regressor prediction (price change %)
            if self.regressor is not None:
                pred_return = self.regressor.predict(features)[0]
                predicted_price = current_price * (1 + pred_return)
                expected_return = float(pred_return * 100)
            else:
                expected_return = None
            
            return {
                "current_price": float(current_price),
                "predicted_price": float(predicted_price) if predicted_price else None,
                "expected_return": expected_return,
                "direction": direction
            }
            
        except Exception as e:
            logger.error(f"Error predicting for {ticker}: {e}")
            return {
                "current_price": current_price,
                "predicted_price": None,
                "expected_return": None,
                "direction": "ERROR"
            }
    
    def predict_consolidated(self, companies: List[Dict]) -> List[Dict]:
        """
        Generate predictions for multiple companies (dashboard view)
        
        Args:
            companies: List of dicts with 'ticker', 'name', 'price'
        
        Returns:
            List of predictions sorted by expected return
        """
        predictions = []
        
        logger.info(f"Starting predictions for {len(companies)} companies...")
        
        for idx, company in enumerate(companies, 1):  # Process all companies
            ticker = company.get('ticker')
            name = company.get('name') or company.get('company')
            price = company.get('price')
            
            if not ticker or not price:
                logger.warning(f"Skipping company {idx}: missing ticker or price - {company}")
                continue
            
            logger.info(f"[{idx}/{len(companies)}] Generating prediction for {name} ({ticker})")
            
            try:
                pred = self.predict_single_company(ticker, float(price))
                pred['company'] = name
                pred['ticker'] = ticker
                predictions.append(pred)
                logger.info(f"✓ [{idx}/{len(companies)}] Completed {name}: {pred['direction']}")
            except Exception as e:
                logger.error(f"✗ [{idx}/{len(companies)}] Failed to predict {name} ({ticker}): {e}", exc_info=True)
                # Add a fallback entry so we don't skip the company
                predictions.append({
                    'company': name,
                    'ticker': ticker,
                    'current_price': float(price),
                    'predicted_price': None,
                    'expected_return': None,
                    'direction': 'ERROR'
                })
            
            # Small delay to avoid rate limiting
            if idx % 10 == 0:
                import time
                time.sleep(0.5)
        
        logger.info(f"Completed {len(predictions)} predictions out of {len(companies)} companies")
        
        # Sort by expected return (descending)
        predictions.sort(key=lambda x: x.get('expected_return') or -999, reverse=True)
        
        return predictions
    
    def is_available(self) -> bool:
        """Check if models are loaded and ready"""
        return self.classifier is not None and self.regressor is not None


# Global instance
_prediction_service = None

def get_prediction_service() -> PricePredictionService:
    """Get or create the singleton prediction service"""
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PricePredictionService()
    return _prediction_service
