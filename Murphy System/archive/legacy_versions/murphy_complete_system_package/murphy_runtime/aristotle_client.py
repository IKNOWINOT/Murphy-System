# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Aristotle API Client
Deterministic verification and validation
"""

import aiohttp
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class AristotleClient:
    """Client for Aristotle API (deterministic verification)"""
    
    def __init__(
        self,
        api_key: str,
        model: str = 'claude-3-haiku-20240307',
        temperature: float = 0.1,
        max_tokens: int = 1024,
        top_p: float = 0.95,
        frequency_penalty: float = 0.0
    ):
        """
        Initialize Aristotle client
        
        Args:
            api_key: Aristotle API key
            model: Model name
            temperature: Sampling temperature (low for deterministic)
            max_tokens: Maximum tokens
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.frequency_penalty = frequency_penalty
        self.base_url = "https://api.anthropic.com/v1"
        
        logger.info(f"Initialized Aristotle client with model {model}")
        logger.info(f"Temperature: {temperature} (deterministic)")
    
    def _format_messages(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        """Format prompt for Anthropic API"""
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "user",
                "content": f"{system_prompt}\n\n{prompt}"
            })
        else:
            messages.append({
                "role": "user",
                "content": prompt
            })
        
        return messages
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        system_prompt: Optional[str] = None
    ) -> Tuple[str, int]:
        """
        Generate text using Aristotle API
        
        Args:
            prompt: The prompt text
            model: Model name (overrides default)
            temperature: Temperature (overrides default)
            max_tokens: Max tokens (overrides default)
            top_p: Top P (overrides default)
            frequency_penalty: Frequency penalty (overrides default)
            system_prompt: System prompt for context
        
        Returns:
            Tuple of (generated_text, tokens_used)
        """
        url = f"{self.base_url}/messages"
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": model or self.model,
            "messages": self._format_messages(prompt, system_prompt),
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "top_p": top_p if top_p is not None else self.top_p
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Aristotle API error {response.status}: {error_text}")
                    
                    data = await response.json()
                    
                    # Extract response
                    content = data['content'][0]['text']
                    tokens_used = data['usage']['input_tokens'] + data['usage']['output_tokens']
                    
                    logger.debug(f"Aristotle response: {len(content)} chars, {tokens_used} tokens")
                    
                    return content, tokens_used
        
        except aiohttp.ClientError as e:
            logger.error(f"Aristotle client error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Aristotle API error: {str(e)}")
            raise
    
    async def verify(
        self,
        content: str,
        criteria: str,
        max_tokens: int = 512
    ) -> Tuple[bool, float, str]:
        """
        Verify content against criteria
        
        Args:
            content: Content to verify
            criteria: Verification criteria
            max_tokens: Maximum tokens for verification response
        
        Returns:
            Tuple of (is_valid, confidence, explanation)
        """
        system_prompt = """You are Aristotle, a verification assistant. Your role is to carefully evaluate content against specified criteria and provide accurate, objective assessments.
        
Respond in the following format:
VALID: [true/false]
CONFIDENCE: [0.0-1.0]
EXPLANATION: [brief explanation of your assessment]"""
        
        prompt = f"""Please verify the following content against these criteria:

Content to verify:
{content}

Criteria:
{criteria}

Provide your assessment in the specified format."""
        
        response, tokens = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.0  # Maximum determinism
        )
        
        # Parse response
        is_valid = False
        confidence = 0.0
        explanation = response
        
        try:
            for line in response.split('\n'):
                line = line.strip().upper()
                if line.startswith('VALID:'):
                    is_valid = 'TRUE' in line
                elif line.startswith('CONFIDENCE:'):
                    confidence = float(line.split(':')[1].strip())
                elif line.startswith('EXPLANATION:'):
                    explanation = line.split(':', 1)[1].strip()
        except Exception as e:
            logger.warning(f"Failed to parse verification response: {str(e)}")
        
        logger.info(f"Verification result: valid={is_valid}, confidence={confidence:.2f}")
        
        return is_valid, confidence, explanation
    
    async def check_compliance(
        self,
        content: str,
        rules: list,
        max_tokens: int = 1024
    ) -> Tuple[dict, str]:
        """
        Check content compliance with rules
        
        Args:
            content: Content to check
            rules: List of rules to check against
            max_tokens: Maximum tokens for response
        
        Returns:
            Tuple of (compliance_results, summary)
        """
        prompt = f"""Check the following content for compliance with these rules:

Content:
{content}

Rules:
{chr(10).join(f'{i+1}. {rule}' for i, rule in enumerate(rules))}

For each rule, provide:
1. Whether the content complies (YES/NO)
2. Any violations found
3. Severity of any violations (LOW/MEDIUM/HIGH)

Format your response as a structured list."""
        
        response, tokens = await self.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.1
        )
        
        # Parse results (simplified)
        results = {
            'compliant': True,
            'violations': [],
            'summary': response
        }
        
        # TODO: Implement detailed parsing
        
        return results, response
    
    async def extract_facts(
        self,
        content: str,
        max_tokens: int = 1024
    ) -> list:
        """
        Extract facts from content
        
        Args:
            content: Content to analyze
            max_tokens: Maximum tokens for response
        
        Returns:
            List of extracted facts
        """
        prompt = f"""Extract the key facts from the following content. Present them as a numbered list of clear, concise statements.

Content:
{content}"""
        
        response, tokens = await self.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.0
        )
        
        # Parse facts (simplified)
        facts = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                facts.append(line)
        
        return facts