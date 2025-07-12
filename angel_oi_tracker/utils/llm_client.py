"""
OpenRouter API Client for AI Trade Intelligence

This module handles communication with OpenRouter API for generating AI trade insights.
Supports multiple models, retry logic, and error handling.

API Documentation: https://openrouter.ai/docs
"""

import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import os

class OpenRouterClient:
    def __init__(self, api_key: str = None, default_model: str = "mistralai/mistral-small-3.2-24b-instruct"):
        """
        Initialize OpenRouter client
        
        Args:
            api_key: OpenRouter API key (defaults to environment variable)
            default_model: Default model to use for requests
        """
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY', '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')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.default_model = default_model
        
        # Available models for rotation (verified working models)
        self.available_models = [
            "mistralai/mistral-small-3.2-24b-instruct",
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemini-flash-1.5",
            "openai/gpt-4o-mini"
        ]
        
        # Rate limiting
        self.rate_limit = 2  # requests per second
        self.last_request_time = 0
        
        # Setup logging
        self.logger = logging.getLogger('openrouter_client')
        
    def _rate_limit_delay(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < (1.0 / self.rate_limit):
            sleep_time = (1.0 / self.rate_limit) - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _make_request(self, payload: Dict, model: str = None, max_retries: int = 3) -> Optional[Dict]:
        """
        Make request to OpenRouter API with retry logic
        
        Args:
            payload: Request payload
            model: Model to use (defaults to self.default_model)
            max_retries: Maximum number of retries
            
        Returns:
            API response or None if failed
        """
        model = model or self.default_model
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://oi-tracker.angelone.in",
            "X-Title": "OI Tracker AI"
        }
        
        for attempt in range(max_retries):
            try:
                self._rate_limit_delay()
                
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt  # Exponential backoff
                    self.logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"API request failed: {response.status_code} - {response.text}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None
    
    def generate_trade_insight(self, market_data: Dict, model: str = None) -> Optional[Dict]:
        """
        Generate trade insight from market data
        
        Args:
            market_data: Structured market data
            model: Model to use
            
        Returns:
            Parsed trade insight or None if failed
        """
        try:
            # Create prompt
            prompt = self._create_trade_prompt(market_data)
            
            # Prepare payload
            payload = {
                "model": model or self.default_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert intraday NIFTY/BANKNIFTY scalper with 15+ years of experience. Analyze the option chain data and provide ONE high-confidence trade setup."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 500,
                "response_format": {"type": "json_object"}
            }
            
            # Make request
            response = self._make_request(payload, model)
            
            if not response:
                return None
            
            # Parse response
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not content:
                return None
            
            # Parse JSON response
            try:
                trade_insight = json.loads(content)
                return self._validate_trade_insight(trade_insight)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {str(e)}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error generating trade insight: {str(e)}")
            return None
    
    def _create_trade_prompt(self, market_data: Dict) -> str:
        """Create structured prompt for trade analysis"""
        
        prompt = f"""
Based on the following market data, suggest ONE high-confidence trade setup for {market_data.get('index', 'NIFTY')}.

Market Context:
- Spot LTP: {market_data.get('spot', {}).get('ltp', 'N/A')}
- PCR (OI): {market_data.get('pcr', {}).get('oi', 'N/A')}
- PCR (Volume): {market_data.get('pcr', {}).get('volume', 'N/A')}
- VWAP: {market_data.get('levels', {}).get('vwap', 'N/A')}
- CPR Top: {market_data.get('levels', {}).get('cpr_top', 'N/A')}
- CPR Bottom: {market_data.get('levels', {}).get('cpr_bottom', 'N/A')}

Option Chain Data:
{self._format_option_chain(market_data.get('option_chain', []))}

Format your response as JSON:
{{
  "bias": "BULLISH/BEARISH/NEUTRAL",
  "strategy": "Brief strategy description",
  "entry_strike": 24000,
  "entry_type": "CE/PE",
  "entry_price": 108.50,
  "stop_loss": 92.00,
  "target": 135.00,
  "confidence": 87,
  "rationale": "Detailed reasoning for the trade setup"
}}

Focus on:
1. High probability setups only (confidence > 70)
2. Clear entry, stop loss, and target levels
3. Technical reasoning based on option chain data
4. Risk-reward ratio of at least 1:2
"""
        return prompt
    
    def _format_option_chain(self, option_chain: List[Dict]) -> str:
        """Format option chain data for prompt"""
        if not option_chain:
            return "No option chain data available"
        
        formatted = []
        for option in option_chain[:10]:  # Limit to first 10 for prompt size
            formatted.append(
                f"- {option.get('strike')} {option.get('type')}: "
                f"LTP={option.get('ltp')}, OI={option.get('oi')}, "
                f"OI_Change={option.get('oi_change')}, IV={option.get('iv')}, "
                f"Delta={option.get('delta')}"
            )
        
        return "\n".join(formatted)
    
    def _validate_trade_insight(self, insight: Dict) -> Optional[Dict]:
        """Validate and clean trade insight"""
        required_fields = ['bias', 'strategy', 'entry_strike', 'entry_type', 
                          'entry_price', 'stop_loss', 'target', 'confidence', 'rationale']
        
        for field in required_fields:
            if field not in insight:
                self.logger.error(f"Missing required field: {field}")
                return None
        
        # Validate data types and ranges
        try:
            insight['entry_strike'] = int(insight['entry_strike'])
            insight['entry_price'] = float(insight['entry_price'])
            insight['stop_loss'] = float(insight['stop_loss'])
            insight['target'] = float(insight['target'])
            insight['confidence'] = int(insight['confidence'])
            
            # Validate ranges
            if not (0 <= insight['confidence'] <= 100):
                self.logger.error(f"Invalid confidence: {insight['confidence']}")
                return None
                
            if insight['entry_type'] not in ['CE', 'PE']:
                self.logger.error(f"Invalid entry type: {insight['entry_type']}")
                return None
                
            if insight['bias'] not in ['BULLISH', 'BEARISH', 'NEUTRAL']:
                self.logger.error(f"Invalid bias: {insight['bias']}")
                return None
                
        except (ValueError, TypeError) as e:
            self.logger.error(f"Data validation error: {str(e)}")
            return None
        
        return insight
    
    def rotate_model(self) -> str:
        """Rotate to next available model"""
        current_index = self.available_models.index(self.default_model)
        next_index = (current_index + 1) % len(self.available_models)
        self.default_model = self.available_models[next_index]
        return self.default_model
    
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return self.available_models.copy()

# Global client instance
openrouter_client = OpenRouterClient() 