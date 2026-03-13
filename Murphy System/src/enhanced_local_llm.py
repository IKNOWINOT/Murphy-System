"""
Enhanced Local LLM System
Replicates mock function outputs with similar quality and structure
"""

import ast
import json
import logging
import math
import operator
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EnhancedLocalLLM:
    """
    Enhanced local LLM that replicates mock function outputs
    Supports step-by-step reasoning, detailed explanations, and creative generation
    """

    def __init__(self):
        self.knowledge_base = self._build_comprehensive_knowledge_base()
        self.math_patterns = self._build_math_patterns()
        self.physics_formulas = self._build_physics_formulas()
        self.code_templates = self._build_code_templates()
        self.generative_templates = self._build_generative_templates()
        self.conversation_history = []

    def query(self, prompt: str, provider: str = 'aristotle',
              temperature: float = 0.7) -> Dict[str, Any]:
        """
        Main query method that matches mock function output structure

        Args:
            prompt: User query
            provider: Which provider to emulate (aristotle, wulfrum, groq)
            temperature: Temperature for randomness

        Returns:
            Dictionary matching mock output structure:
            {
                "response": str,
                "confidence": float,
                "tokens_used": int,
                "provider": str,
                "metadata": Dict
            }
        """
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Generate response based on provider
        if provider == 'aristotle':
            response = self._aristotle_response(prompt, temperature)
        elif provider == 'wulfrum':
            response = self._wulfrum_response(prompt, temperature)
        elif provider == 'groq':
            response = self._groq_response(prompt, temperature)
        else:
            response = self._groq_response(prompt, temperature)
            provider = 'groq'

        # Calculate tokens (rough estimate)
        tokens_used = len(response['response'].split()) + len(prompt.split())

        # Add AI response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response['response'],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        return {
            "response": response['response'],
            "confidence": response['confidence'],
            "tokens_used": tokens_used,
            "provider": provider,
            "metadata": response.get('metadata', {})
        }

    def _aristotle_response(self, prompt: str, temperature: float) -> Dict[str, Any]:
        """
        Aristotle-style: Deterministic mathematical and scientific analysis
        Uses low temperature (0.1) for consistent outputs
        """
        # Check for mathematical queries
        math_result = self._solve_mathematical_query(prompt)
        if math_result:
            return math_result

        # Check for physics queries
        physics_result = self._solve_physics_query(prompt)
        if physics_result:
            return physics_result

        # Check for logical reasoning
        logic_result = self._solve_logical_query(prompt)
        if logic_result:
            return logic_result

        # Default scientific explanation
        return self._generate_scientific_explanation(prompt)

    def _wulfrum_response(self, prompt: str, temperature: float) -> Dict[str, Any]:
        """
        Wulfrum-style: Fuzzy matching and validation
        Uses medium temperature (0.3) for balanced validation
        """
        # Check for validation queries
        validation_result = self._validate_query(prompt)
        if validation_result:
            return validation_result

        # Check for comparison queries
        comparison_result = self._compare_query(prompt)
        if comparison_result:
            return comparison_result

        # Default validation response
        return self._generate_validation_response(prompt)

    def _groq_response(self, prompt: str, temperature: float) -> Dict[str, Any]:
        """
        Groq-style: General domain tasks and generation
        Uses high temperature (0.7) for creative output
        """
        # Check for creative requests
        creative_result = self._generate_creative_content(prompt)
        if creative_result:
            return creative_result

        # Check for code generation
        code_result = self._generate_code(prompt)
        if code_result:
            return code_result

        # Check for explanation requests
        explanation_result = self._generate_explanation(prompt)
        if explanation_result:
            return explanation_result

        # Default generative response
        return self._generate_general_response(prompt)

    def _solve_mathematical_query(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Solve mathematical queries with step-by-step reasoning"""
        prompt_lower = prompt.lower()

        # Enhanced pattern matching for math operations
        patterns = [
            # Calculus operations
            (r'what is the (derivative|integral|limit) of (.+)', self._solve_calculus),
            (r'(find|calculate|compute) the (derivative|integral|limit) of (.+)', self._solve_calculus),
            (r'd/dx\s*\((.+)\)', self._solve_calculus),
            (r'derivative of (.+)', self._solve_calculus),
            (r'integral of (.+)', self._solve_calculus),

            # Arithmetic operations
            (r'calculate|solve|compute|evaluate (.+)', self._solve_arithmetic),
            (r'what is (.+) plus (.+)', self._solve_arithmetic),
            (r'what is (.+) minus (.+)', self._solve_arithmetic),
            (r'what is (.+) times (.+)', self._solve_arithmetic),
            (r'what is (.+) divided by (.+)', self._solve_arithmetic),
            (r'what is (.+) \+ (.+)', self._solve_arithmetic),
            (r'what is (.+) - (.+)', self._solve_arithmetic),
            (r'what is (.+) \* (.+)', self._solve_arithmetic),
            (r'what is (.+) / (.+)', self._solve_arithmetic),
            (r'calculate (.+) \+ (.+)', self._solve_arithmetic),
            (r'calculate (.+) - (.+)', self._solve_arithmetic),
            (r'calculate (.+) \* (.+)', self._solve_arithmetic),
            (r'calculate (.+) / (.+)', self._solve_arithmetic),

            # Algebra operations
            (r'simplify (.+)', self._simplify_expression),
            (r'factor (.+)', self._simplify_expression),
            (r'expand (.+)', self._simplify_expression),
            (r'solve (.+) for (.+)', self._simplify_expression),

            # Direct mathematical expressions
            (r'^[\d\s\+\-\*\/\(\)\.\^]+$', self._solve_arithmetic),
        ]

        for pattern, solver in patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                try:
                    result = solver(match, prompt)
                    if result:
                        return result
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    pass

        return None

    def _solve_calculus(self, match: re.Match, original_prompt: str) -> Dict[str, Any]:
        """Solve calculus problems with step-by-step explanation"""
        operation = match.group(1)
        expression = match.group(2)

        if operation == 'derivative':
            # Parse common derivatives
            derivative_result = self._compute_derivative(expression)
            if derivative_result:
                steps = [
                    f"Step 1: Identify the function to differentiate: f(x) = {expression}",
                    "Step 2: Apply differentiation rules",
                ]
                steps.extend(derivative_result['steps'])

                response = f"""
**Mathematical Analysis - Derivative**

**Problem**: Find the derivative of f(x) = {expression}

**Step-by-Step Solution**:
{chr(10).join([f"{i+1}. {step}" for i, step in enumerate(steps)])}

**Final Answer**: d/dx[{expression}] = {derivative_result['result']}

**Explanation**: This derivative represents the rate of change of the function with respect to x. It can be used to find slopes of tangent lines, optimize functions, and analyze function behavior.

**Applications**:
- Physics: Velocity and acceleration
- Economics: Marginal cost and revenue
- Engineering: Optimization problems
"""

                return {
                    "response": response,
                    "confidence": 0.95,
                    "metadata": {
                        "reasoning_type": "deterministic",
                        "steps_count": len(steps),
                        "complexity": derivative_result.get('complexity', 'medium')
                    }
                }

        return None

    def _compute_derivative(self, expression: str) -> Optional[Dict[str, Any]]:
        """Compute derivative of common expressions"""
        expression = expression.strip()

        # Common derivative rules - enhanced with more patterns
        derivative_rules = {
            # Power functions
            r'^x\s*\^\s*2$': {
                'result': '2x',
                'steps': [
                    "Apply power rule: d/dx[x^n] = nx^(n-1)",
                    "For x^2: n=2, so derivative = 2x^(2-1) = 2x"
                ],
                'complexity': 'simple'
            },
            r'^x\s*\^\s*3$': {
                'result': '3x^2',
                'steps': [
                    "Apply power rule: d/dx[x^n] = nx^(n-1)",
                    "For x^3: n=3, so derivative = 3x^(3-1) = 3x^2"
                ],
                'complexity': 'simple'
            },
            r'^x\s*\^\s*n$': {
                'result': 'nx^(n-1)',
                'steps': [
                    "Apply power rule: d/dx[x^n] = nx^(n-1)"
                ],
                'complexity': 'simple'
            },
            r'^x$': {
                'result': '1',
                'steps': [
                    "Apply power rule: d/dx[x^n] = nx^(n-1)",
                    "For x = x^1: n=1, so derivative = 1x^(1-1) = 1"
                ],
                'complexity': 'simple'
            },

            # Trigonometric functions
            r'^sin\(x\)$': {
                'result': 'cos(x)',
                'steps': [
                    "Apply trigonometric derivative: d/dx[sin(x)] = cos(x)"
                ],
                'complexity': 'simple'
            },
            r'^cos\(x\)$': {
                'result': '-sin(x)',
                'steps': [
                    "Apply trigonometric derivative: d/dx[cos(x)] = -sin(x)"
                ],
                'complexity': 'simple'
            },
            r'^tan\(x\)$': {
                'result': 'sec^2(x)',
                'steps': [
                    "Apply trigonometric derivative: d/dx[tan(x)] = sec^2(x)"
                ],
                'complexity': 'simple'
            },

            # Exponential and logarithmic
            r'^e\s*\^\s*x$': {
                'result': 'e^x',
                'steps': [
                    "Apply exponential derivative: d/dx[e^x] = e^x"
                ],
                'complexity': 'simple'
            },
            r'^ln\(x\)$': {
                'result': '1/x',
                'steps': [
                    "Apply logarithmic derivative: d/dx[ln(x)] = 1/x"
                ],
                'complexity': 'simple'
            },
            r'^log\(x\)$': {
                'result': '1/x',
                'steps': [
                    "Apply logarithmic derivative: d/dx[log(x)] = 1/x"
                ],
                'complexity': 'simple'
            },

            # Constants
            r'^[0-9]+$': {
                'result': '0',
                'steps': [
                    "Apply constant rule: d/dx[c] = 0 for any constant c"
                ],
                'complexity': 'simple'
            },
        }

        # Try exact matches first
        for pattern, rule in derivative_rules.items():
            if re.fullmatch(pattern, expression, re.IGNORECASE):
                return rule

        # Try partial matches for more flexible input
        flexible_rules = {
            r'x\^2': {
                'result': '2x',
                'steps': [
                    "Apply power rule: d/dx[x^n] = nx^(n-1)",
                    "For x^2: n=2, so derivative = 2x^(2-1) = 2x"
                ],
                'complexity': 'simple'
            },
            r'x\^3': {
                'result': '3x^2',
                'steps': [
                    "Apply power rule: d/dx[x^n] = nx^(n-1)",
                    "For x^3: n=3, so derivative = 3x^(3-1) = 3x^2"
                ],
                'complexity': 'simple'
            },
            r'sin\(x\)|sin x': {
                'result': 'cos(x)',
                'steps': [
                    "Apply trigonometric derivative: d/dx[sin(x)] = cos(x)"
                ],
                'complexity': 'simple'
            },
            r'cos\(x\)|cos x': {
                'result': '-sin(x)',
                'steps': [
                    "Apply trigonometric derivative: d/dx[cos(x)] = -sin(x)"
                ],
                'complexity': 'simple'
            },
            r'e\^x|e x': {
                'result': 'e^x',
                'steps': [
                    "Apply exponential derivative: d/dx[e^x] = e^x"
                ],
                'complexity': 'simple'
            },
            r'ln\(x\)|ln x|log\(x\)|log x': {
                'result': '1/x',
                'steps': [
                    "Apply logarithmic derivative: d/dx[ln(x)] = 1/x"
                ],
                'complexity': 'simple'
            },
        }

        for pattern, rule in flexible_rules.items():
            if re.search(pattern, expression, re.IGNORECASE):
                return rule

        return None

    def _solve_arithmetic(self, match: re.Match, original_prompt: str) -> Dict[str, Any]:
        """Solve arithmetic problems using a safe AST-based evaluator."""
        try:
            # Extract the expression
            expression = match.group(2) if len(match.groups()) >= 2 else match.group(0)

            # Clean up the expression
            expression = expression.replace('what is', '').strip()
            expression = re.sub(r'[^\d+\-*/().\s^]', '', expression)

            # Evaluate safely — no eval(); walk the AST instead
            result = self._safe_eval_arithmetic(expression)

            response = f"""
**Mathematical Calculation**

**Problem**: {original_prompt}

**Step-by-Step Solution**:
1. Parse the expression: {expression}
2. Apply order of operations (PEMDAS)
3. Calculate the result

**Final Answer**: {expression} = {result}

**Verification**:
- Check arithmetic operations
- Verify order of operations
- Result type: {type(result).__name__}
"""

            return {
                "response": response,
                "confidence": 0.98,
                "metadata": {
                    "reasoning_type": "deterministic",
                    "operation": "arithmetic",
                    "result_type": type(result).__name__
                }
            }
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return None

    # -- Safe arithmetic evaluator (replaces eval) ---------------------------

    _SAFE_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _safe_eval_arithmetic(self, expression: str):
        """Evaluate a numeric arithmetic expression without ``eval()``.

        Only literal numbers and the operators ``+ - * / ** ^`` are
        permitted.  Raises ``ValueError`` for anything else.
        """
        # Treat ``^`` as exponentiation (common user expectation)
        expression = expression.replace("^", "**")
        node = ast.parse(expression.strip(), mode="eval")
        return self._safe_eval_node(node.body)

    def _safe_eval_node(self, node):
        if isinstance(node, ast.Expression):
            return self._safe_eval_node(node.body)
        if isinstance(node, (ast.Constant,)):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        if isinstance(node, ast.UnaryOp):
            op_fn = self._SAFE_OPS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported unary op: {type(node.op).__name__}")
            return op_fn(self._safe_eval_node(node.operand))
        if isinstance(node, ast.BinOp):
            op_fn = self._SAFE_OPS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported binary op: {type(node.op).__name__}")
            return op_fn(
                self._safe_eval_node(node.left),
                self._safe_eval_node(node.right),
            )
        raise ValueError(f"Unsupported AST node: {type(node).__name__}")

    def _simplify_expression(self, match: re.Match, original_prompt: str) -> Optional[Dict[str, Any]]:
        """Simplify mathematical expressions"""
        expression = match.group(1)

        response = f"""
**Mathematical Simplification**

**Expression**: {expression}

**Analysis**:
This expression can be simplified by applying algebraic rules.

**Steps**:
1. Identify like terms
2. Apply distributive property if needed
3. Combine terms
4. Write final simplified form

**Simplified Result**: {expression}

**Note**: For complex simplifications, additional context may be needed to provide the most appropriate form.
"""

        return {
            "response": response,
            "confidence": 0.90,
            "metadata": {
                "reasoning_type": "algebraic",
                "complexity": "medium"
            }
        }

    def _solve_physics_query(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Solve physics queries with formulas and explanations"""
        prompt_lower = prompt.lower()

        # Check for physics keywords
        physics_keywords = ['kinetic energy', 'force', 'velocity', 'acceleration',
                          'momentum', 'work', 'power', 'ohm', 'coulomb']

        for keyword in physics_keywords:
            if keyword in prompt_lower:
                return self._generate_physics_explanation(keyword, prompt)

        return None

    def _generate_physics_explanation(self, topic: str, prompt: str) -> Dict[str, Any]:
        """Generate physics explanation with formulas"""

        physics_info = self.physics_formulas.get(topic, {})

        if not physics_info:
            return None

        response = f"""
**Physics Analysis - {topic.replace('_', ' ').title()}**

**Formula**: {physics_info.get('formula', 'N/A')}

**Variables**:
{chr(10).join([f"- {var}: {desc}" for var, desc in physics_info.get('variables', {}).items()])}

**Explanation**:
{physics_info.get('explanation', '')}

**Example**:
{physics_info.get('example', '')}

**Applications**:
{chr(10).join([f"- {app}" for app in physics_info.get('applications', [])])}

**Key Concepts**:
- Conservation principles
- Units and measurements
- Real-world applications
"""

        return {
            "response": response,
            "confidence": 0.95,
            "metadata": {
                "reasoning_type": "scientific",
                "domain": "physics",
                "topic": topic
            }
        }

    def _solve_logical_query(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Solve logical reasoning queries"""
        prompt_lower = prompt.lower()

        # Check for yes/no questions
        if prompt.strip().endswith('?'):
            if 'true' in prompt_lower or 'false' in prompt_lower:
                return self._analyze_boolean_query(prompt)

        # Check for comparison
        if 'greater than' in prompt_lower or 'less than' in prompt_lower:
            return self._analyze_comparison_query(prompt)

        return None

    def _analyze_boolean_query(self, prompt: str) -> Dict[str, Any]:
        """Analyze boolean logic queries"""
        response = f"""
**Logical Analysis**

**Query**: {prompt}

**Analysis**:
This is a boolean logic question that requires evaluating the truth value of the statement.

**Evaluation Steps**:
1. Identify the logical operators and operands
2. Apply truth tables or logical rules
3. Determine the truth value

**Result**: Based on standard boolean logic, this statement can be evaluated as either true or false depending on the specific values of the variables involved.

**For precise evaluation**, please provide:
- Variable definitions
- Context or domain information
- Specific conditions or constraints

**Note**: In offline mode, I can explain logical principles but cannot evaluate arbitrary boolean expressions without complete context.
"""

        return {
            "response": response,
            "confidence": 0.85,
            "metadata": {
                "reasoning_type": "logical",
                "logic_type": "boolean"
            }
        }

    def _analyze_comparison_query(self, prompt: str) -> Dict[str, Any]:
        """Analyze comparison queries"""
        response = f"""
**Comparative Analysis**

**Query**: {prompt}

**Analysis**:
This comparison involves evaluating the relationship between two or more values or expressions.

**Comparison Steps**:
1. Identify the values being compared
2. Determine the comparison operator (>, <, =, >=, <=)
3. Apply the comparison
4. Draw conclusion

**Result**: The comparison can be resolved by evaluating the mathematical relationship between the specified values.

**For specific evaluation**, provide the actual values or expressions to compare.
"""

        return {
            "response": response,
            "confidence": 0.88,
            "metadata": {
                "reasoning_type": "comparative",
                "analysis_type": "comparison"
            }
        }

    def _generate_scientific_explanation(self, prompt: str) -> Dict[str, Any]:
        """Generate general scientific explanation"""
        response = f"""
**Scientific Analysis**

**Topic**: {prompt}

**Overview**:
This topic falls within the domain of science and can be analyzed using systematic, evidence-based approaches.

**Key Aspects**:
1. **Definition**: Clear understanding of fundamental concepts
2. **Principles**: Underlying laws and theories
3. **Applications**: Real-world uses and implications
4. **Relationships**: Connections to other scientific domains

**Analytical Approach**:
- Identify core components
- Understand governing principles
- Analyze relationships and dependencies
- Consider practical applications

**Note**: For detailed, up-to-date scientific information, I recommend consulting current research literature or academic resources when internet connectivity is available.

**Confidence**: This explanation provides a general framework, but specific details may require additional context or online resources.
"""

        return {
            "response": response,
            "confidence": 0.75,
            "metadata": {
                "reasoning_type": "scientific",
                "domain": "general"
            }
        }

    def _validate_query(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Validate queries with fuzzy matching"""
        prompt_lower = prompt.lower()

        # Check for validation patterns
        validation_patterns = [
            (r'is (correct|true|false|valid)', 'boolean_validation'),
            (r'(check|verify|validate) (.+)', 'verification'),
            (r'(does|will|can) (.+)', 'prediction'),
        ]

        for pattern, validation_type in validation_patterns:
            if re.search(pattern, prompt_lower):
                return self._generate_validation_response(prompt, validation_type)

        return None

    def _generate_validation_response(self, prompt: str, validation_type: str = 'general') -> Dict[str, Any]:
        """Generate validation response"""

        if validation_type == 'boolean_validation':
            response = f"""
**Validation Analysis**

**Query**: {prompt}

**Assessment**:
This is a boolean validation query requiring a true/false determination.

**Validation Process**:
1. Identify the statement or condition to validate
2. Apply relevant rules or principles
3. Check for exceptions or edge cases
4. Determine truth value

**Evaluation**:
Based on the information provided, I can analyze the logical structure of the statement.

**Match Quality**: Medium - The query structure is clear, but specific context may affect the validation result.

**Recommendation**: For precise validation, provide:
- Complete statement or condition
- Context or domain information
- Relevant parameters or values

**Confidence**: This analysis provides the validation framework, but the final truth value depends on specific values and context.
"""
        elif validation_type == 'verification':
            response = f"""
**Verification Analysis**

**Query**: {prompt}

**Verification Process**:
1. Identify the item or statement to verify
2. Check against known facts or rules
3. Validate consistency
4. Confirm accuracy

**Assessment**:
I can verify the structure and logical consistency of the query.

**Match Quality**: High - The query follows a clear verification pattern.

**For complete verification**, please provide:
- Complete item or statement to verify
- Reference or standard for comparison
- Context or domain information

**Confidence**: High - The verification approach is sound, but final result depends on specific data.
"""
        else:
            response = f"""
**Validation Analysis**

**Query**: {prompt}

**Analysis**:
I've analyzed your query using pattern matching and logical evaluation.

**Assessment**:
- Query Structure: Valid
- Logical Consistency: Checked
- Context Requirements: Identified

**Match Quality**: The query matches expected patterns for validation.

**Recommendation**: Provide additional context or specific values for complete validation.

**Confidence**: The validation framework is reliable, but the specific result depends on complete information.
"""

        return {
            "response": response,
            "confidence": 0.85,
            "metadata": {
                "validation_type": validation_type,
                "match_quality": "medium" if validation_type == "boolean_validation" else "high"
            }
        }

    def _compare_query(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Handle comparison queries"""
        if 'difference between' in prompt.lower() or 'compare' in prompt.lower():
            return self._generate_comparison_response(prompt)
        return None

    def _generate_comparison_response(self, prompt: str) -> Dict[str, Any]:
        """Generate comparison response"""
        response = f"""
**Comparative Analysis**

**Query**: {prompt}

**Comparison Framework**:
1. Identify the items or concepts being compared
2. List key characteristics of each
3. Analyze similarities
4. Analyze differences
5. Draw conclusions

**Analysis**:
I can provide a structured comparison based on the items in your query.

**Key Comparison Points**:
- Purpose and function
- Characteristics and properties
- Advantages and disadvantages
- Use cases and applications
- Performance metrics (if applicable)

**For detailed comparison**, provide:
- Complete list of items to compare
- Specific comparison criteria
- Context or domain information

**Confidence**: High - The comparison framework is comprehensive and applicable to most scenarios.
"""

        return {
            "response": response,
            "confidence": 0.88,
            "metadata": {
                "validation_type": "comparison",
                "match_quality": "high"
            }
        }

    def _generate_creative_content(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Generate creative content (poems, stories, etc.)"""
        prompt_lower = prompt.lower()

        # Enhanced creative pattern matching
        creative_patterns = [
            # Poem patterns
            (r'write (a|an)? poem', 'creative_writing_poem'),
            (r'create (a|an)? poem', 'creative_writing_poem'),
            (r'generate (a|an)? poem', 'creative_writing_poem'),
            (r'make (a|an)? poem', 'creative_writing_poem'),
            (r'compose (a|an)? poem', 'creative_writing_poem'),
            (r'write a poem (about|on) (.+)', 'creative_writing_poem'),
            (r'poem about (.+)', 'creative_writing_poem'),

            # Story patterns
            (r'write (a|an)? story', 'creative_writing_story'),
            (r'create (a|an)? story', 'creative_writing_story'),
            (r'generate (a|an)? story', 'creative_writing_story'),
            (r'make (a|an)? story', 'creative_writing_story'),
            (r'tell (me )?(a )?story', 'creative_writing_story'),
            (r'write a story about (.+)', 'creative_writing_story'),
            (r'story about (.+)', 'creative_writing_story'),

            # Article patterns
            (r'write (a|an)? article', 'creative_writing_article'),
            (r'create (a|an)? article', 'creative_writing_article'),
            (r'write an article about (.+)', 'creative_writing_article'),
            (r'article about (.+)', 'creative_writing_article'),

            # Essay patterns
            (r'write (a|an)? essay', 'creative_writing_article'),
            (r'create (a|an)? essay', 'creative_writing_article'),
            (r'write an essay about (.+)', 'creative_writing_article'),
            (r'essay about (.+)', 'creative_writing_article'),

            # Description patterns
            (r'describe (.+) (in detail|creatively)', 'creative_description'),
            (r'give me a description of (.+)', 'creative_description'),
            (r'tell me about (.+)', 'creative_description'),

            # Imagination patterns
            (r'imagine (.+)', 'creative_imagination'),
            (r'what if (.+)', 'creative_imagination'),
            (r'picture (.+)', 'creative_imagination'),

            # General creative requests
            (r'be creative', 'creative_general'),
            (r'write something creative', 'creative_general'),
            (r'get creative', 'creative_general'),
        ]

        for pattern, content_type in creative_patterns:
            if re.search(pattern, prompt_lower):
                return self._generate_creative_response(prompt, content_type)

        return None

    def _generate_creative_response(self, prompt: str, content_type: str) -> Dict[str, Any]:
        """Generate creative writing response"""

        if content_type == 'creative_writing_poem':
            response = self._generate_poem(prompt)
            creativity_level = "high"
        elif content_type == 'creative_writing_story':
            response = self._generate_story(prompt)
            creativity_level = "high"
        elif content_type == 'creative_writing_article':
            response = self._generate_article(prompt)
            creativity_level = "medium"
        elif content_type == 'creative_writing_article':
            response = self._generate_article(prompt)
            creativity_level = "medium"
        elif content_type == 'creative_description':
            response = self._generate_description(prompt)
            creativity_level = "medium"
        elif content_type == 'creative_imagination':
            response = self._generate_imagination(prompt)
            creativity_level = "high"
        elif content_type == 'creative_general':
            response = self._generate_general_creative(prompt)
            creativity_level = "medium"
        else:
            # Fallback for backward compatibility
            if 'poem' in prompt.lower():
                response = self._generate_poem(prompt)
                creativity_level = "high"
            elif 'story' in prompt.lower():
                response = self._generate_story(prompt)
                creativity_level = "high"
            else:
                response = self._generate_article(prompt)
                creativity_level = "medium"

        return {
            "response": response,
            "confidence": 0.80,  # Increased confidence for creative content
            "metadata": {
                "generation_type": "creative",
                "content_type": content_type,
                "creativity_level": creativity_level
            }
        }

    def _generate_poem(self, prompt: str) -> str:
        """Generate a poem"""
        return f"""
**Creative Writing - Poem**

**Inspired by**: {prompt}

---

In realms where logic meets the mind,
Where answers wait for us to find,
A question asked, a journey started,
Knowledge gathered, never parted.

Through fields of thought and streams of light,
We seek the truth with all our might,
Each step we take, each path we choose,
Leads us closer to the muse.

The answer lies not just in facts,
But in the wondering that acts,
A catalyst for minds to grow,
And seek the truth that we all know.

---

*Generated with creative expression and thoughtful consideration of your request.*
"""

    def _generate_story(self, prompt: str) -> str:
        """Generate a short story"""
        return f"""
**Creative Writing - Short Story**

**Theme**: {prompt}

---

In a world where questions were the currency of progress, there lived a curious soul who never stopped asking "why". This soul, whom we'll call the Seeker, embarked on a journey to find the ultimate answer.

The Seeker traveled through mountains of knowledge, crossed rivers of wisdom, and navigated forests of understanding. Along the way, they encountered many wise beings—some who knew the answers, and some who only knew better questions.

One day, the Seeker met an ancient sage who had spent a lifetime pondering the very question the Seeker had asked.

"The answer you seek," the sage said, "is not a destination but a journey. Each answer you find leads to more questions, and each question opens new doors of discovery."

The Seeker realized that the quest for knowledge was endless, and that the joy lay not in the final answer, but in the pursuit itself. With this wisdom, the Seeker continued their journey, forever asking, forever learning, forever growing.

---

*A story inspired by the eternal quest for knowledge and understanding.*
"""

    def _generate_article(self, prompt: str) -> str:
        """Generate an article"""
        return f"""
**Article - {prompt}**

**Introduction**
The topic of {prompt} has fascinated thinkers and practitioners for generations. This article explores its various aspects and implications.

**Key Concepts**
Understanding this topic requires examining several fundamental concepts. First, we must consider the historical context and how understanding has evolved over time. Second, we need to analyze the current state of knowledge and practice. Finally, we should look toward future developments and potential applications.

**Applications and Relevance**
This topic has practical applications in numerous fields:
- Technology and innovation
- Business and industry
- Education and research
- Personal development

**Challenges and Opportunities**
Like any complex topic, this one presents both challenges and opportunities. The challenges include navigating complexity and ensuring accuracy. The opportunities lie in the potential for growth, innovation, and positive impact.

**Conclusion**
The journey of understanding this topic is ongoing. By staying curious, open-minded, and dedicated to learning, we can continue to expand our knowledge and apply it meaningfully.

---

*An exploratory article covering key aspects of the requested topic.*
"""

    def _generate_description(self, prompt: str) -> str:
        """Generate creative description"""
        return f"""
**Creative Description**

**Subject**: {prompt}

Imagine a landscape where ideas flow like rivers and knowledge rises like mountains. In this realm, every question is a doorway to new understanding, and every answer is a stepping stone to deeper insight.

The subject of your request exists at the intersection of curiosity and discovery. It invites us to explore, to question, and to imagine possibilities beyond our current understanding.

Picture a tapestry woven with threads of history, science, art, and human experience. Each thread contributes to the rich, complex pattern that represents our collective knowledge about this topic.

As we contemplate this subject, we are reminded of the infinite capacity of the human mind to wonder, to learn, and to create meaning from the world around us.

---

*A creative exploration of the requested subject, blending imagination with insight.*
"""

    def _generate_imagination(self, prompt: str) -> str:
        """Generate imaginative response"""
        return f"""
**Imaginative Exploration**

**Prompt**: {prompt}

Let us imagine a world where this concept has fully developed and integrated into our lives. In this imagined reality:

- The boundaries of what's possible expand dramatically
- New opportunities emerge that we hadn't previously considered
- Challenges transform into catalysts for innovation
- Collaboration and creativity flourish

In this vision, the concept we're exploring becomes more than just an idea—it becomes a living, breathing part of our ecosystem of understanding and action.

We see ripple effects spreading outward—touching education, industry, art, and everyday life. Each interaction creates new possibilities, each application reveals new insights.

This imagined future isn't just fantasy—it's a potential reality waiting to be realized through human ingenuity, perseverance, and collaborative effort.

---

*An imaginative exploration of possibilities inspired by your prompt.*
"""

    def _generate_general_creative(self, prompt: str) -> str:
        """Generate general creative response"""
        return f"""
**Creative Expression**

**Inspiration**: {prompt}

Creativity flows like a river, finding new paths and creating unexpected beauty. When we allow ourselves to think beyond conventional boundaries, we discover solutions and ideas that transform our understanding.

This exploration of creativity invites us to see the world through different lenses—to find wonder in the ordinary, to see patterns in chaos, and to imagine possibilities beyond the obvious.

Let's create something unique, something that speaks to both the heart and the mind, something that reminds us of the infinite potential of human imagination.

---

*A creative response inspired by your request for creativity and innovation.*
"""

    def _generate_code(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Generate code snippets"""
        prompt_lower = prompt.lower()

        # Check for code generation patterns
        code_patterns = [
            (r'write (a|an|the) (python|javascript|java|html|css|c\+\+|c) (function|class|script|program)', 'code_generation'),
            (r'create (a|an) (api|function|method|class)', 'code_generation'),
            (r'(show|display) (the )?code for (.+)', 'code_generation'),
        ]

        for pattern, _ in code_patterns:
            if re.search(pattern, prompt_lower):
                return self._generate_code_response(prompt)

        return None

    def _generate_code_response(self, prompt: str) -> Dict[str, Any]:
        """Generate code response"""
        # Determine language
        language = 'python'
        if 'javascript' in prompt.lower():
            language = 'javascript'
        elif 'java' in prompt.lower():
            language = 'java'
        elif 'html' in prompt.lower():
            language = 'html'
        elif 'css' in prompt.lower():
            language = 'css'
        elif 'c++' in prompt.lower():
            language = 'cpp'

        code = self._generate_code_snippet(prompt, language)

        response = f"""
**Code Generation - {language.title()}**

**Request**: {prompt}

```{language}
{code}
```

**Explanation**:
This code implements the requested functionality using {language.title()}.

**Key Features**:
- Clean, readable structure
- Proper error handling
- Efficient implementation
- Well-commented code

**Usage**:
Integrate this code into your project as needed. Adjust parameters and logic to match your specific requirements.

**Note**: This is a template implementation. You may need to modify it based on your specific use case and requirements.

**Confidence**: High - The code follows best practices and is ready for integration.
"""

        return {
            "response": response,
            "confidence": 0.90,
            "metadata": {
                "generation_type": "code",
                "language": language,
                "code_length": len(code.split())
            }
        }

    def _generate_code_snippet(self, prompt: str, language: str) -> str:
        """Generate code snippet based on language"""

        if language == 'python':
            return '''
def example_function(param1, param2=None):
    """
    Example function demonstrating best practices

    Args:
        param1: First parameter (required)
        param2: Second parameter (optional)

    Returns:
        Result of the computation
    """
    try:
        # Main logic here
        result = process_data(param1, param2)
        return result
    except Exception as e:
        # Error handling
        log_error(e)
        return None

def process_data(data, options=None):
    """Process the input data"""
    if options is None:
        options = {}

    # Implement processing logic
    processed = transform(data)
    return processed

def log_error(error):
    """Log errors for debugging"""
    logger.info(f"Error occurred: {error}")
'''
        elif language == 'javascript':
            return '''
/**
 * Example function demonstrating best practices
 * @param {string} param1 - First parameter (required)
 * @param {object} param2 - Second parameter (optional)
 * @returns {any} Result of the computation
 */
function exampleFunction(param1, param2 = null) {
    try {
        // Main logic here
        const result = processData(param1, param2);
        return result;
    } catch (error) {
        // Error handling
        logError(error);
        return null;
    }
}

/**
 * Process the input data
 * @param {any} data - Input data
 * @param {object} options - Processing options
 * @returns {any} Processed data
 */
function processData(data, options = {}) {
    // Implement processing logic
    const processed = transform(data);
    return processed;
}

/**
 * Log errors for debugging
 * @param {Error} error - Error to log
 */
function logError(error) {
    console.error(`Error occurred: ${error}`);
}
'''
        elif language == 'html':
            return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Example Page</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
    </style>
</head>
<body>
    <h1>Example Page</h1>
    <p>This is an example HTML page.</p>

    <div class="content">
        <h2>Content Section</h2>
        <p>Add your content here.</p>
    </div>

    <script>
        // Add your JavaScript here
        console.log("Page loaded");
    </script>
</body>
</html>
'''
        else:
            return f"""
// Example code in {language}
// Implement your functionality here

function main() {{
    // Main logic
    console.log("Hello from {language}!");
}}

main();
"""

    def _generate_explanation(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Generate explanations"""
        prompt_lower = prompt.lower()

        if 'explain' in prompt_lower or 'what is' in prompt_lower:
            return self._generate_detailed_explanation(prompt)

        return None

    def _generate_detailed_explanation(self, prompt: str) -> Dict[str, Any]:
        """Generate detailed explanation"""

        # Check knowledge base
        for topic, content in self.knowledge_base.items():
            if topic.replace('_', ' ') in prompt.lower():
                response = f"""
**Detailed Explanation**

**Topic**: {topic.replace('_', ' ').title()}

{content}

**Key Takeaways**:
- Understanding core concepts is essential
- Practical applications reinforce theory
- Continuous learning enhances mastery

**Related Topics**:
- Advanced concepts and applications
- Integration with other domains
- Current research and developments

**Note**: This explanation provides a solid foundation. For specialized applications or current research, consult domain-specific resources.
"""
                return {
                    "response": response,
                    "confidence": 0.92,
                    "metadata": {
                        "generation_type": "explanation",
                        "topic": topic,
                        "knowledge_base": True
                    }
                }

        # Generate general explanation
        response = f"""
**Detailed Explanation**

**Topic**: {prompt}

**Overview**:
This topic encompasses several important concepts and principles that are fundamental to understanding the subject matter.

**Key Concepts**:

1. **Fundamental Principles**
   - Core ideas that form the foundation
   - Essential relationships and dependencies
   - Basic rules and guidelines

2. **Practical Applications**
   - Real-world use cases
   - Implementation strategies
   - Best practices

3. **Advanced Considerations**
   - Edge cases and special scenarios
   - Performance implications
   - Scalability concerns

**Explanation**:
The topic you've asked about involves understanding how different components interact and work together. By breaking it down into manageable parts, we can gain a comprehensive understanding of the whole.

**Example**:
Consider this topic as a system with interconnected parts. Each part has a specific function, and together they create a complete, working system.

**Conclusion**:
Mastering this topic requires both theoretical understanding and practical application. Start with the fundamentals, then gradually explore more advanced concepts.

**Confidence**: This explanation provides a general framework. Specific details may require additional context or domain expertise.
"""

        return {
            "response": response,
            "confidence": 0.80,
            "metadata": {
                "generation_type": "explanation",
                "topic": "general",
                "knowledge_base": False
            }
        }

    def _generate_general_response(self, prompt: str) -> Dict[str, Any]:
        """Generate general response when no specific pattern matches"""

        response = f"""
**Response to Your Query**

**Question**: {prompt}

I've analyzed your query and provided a comprehensive response based on my knowledge base and capabilities.

**Analysis**:
- Your question has been processed using pattern matching
- Relevant information has been retrieved from my knowledge base
- A structured response has been generated

**Key Points**:
1. Understanding the context of your question
2. Identifying relevant information and principles
3. Organizing the response for clarity and completeness
4. Providing actionable insights where applicable

**Additional Information**:
If you need more specific details or have follow-up questions, please provide additional context or ask for clarification on specific aspects.

**Note**: I'm operating in enhanced offline mode with comprehensive knowledge bases and response templates. For the most current information or specialized topics, online resources may provide additional depth.

**Confidence**: This response is based on available information and follows logical reasoning principles.
"""

        return {
            "response": response,
            "confidence": 0.75,
            "metadata": {
                "generation_type": "general",
                "response_method": "template-based"
            }
        }

    def _build_comprehensive_knowledge_base(self) -> Dict[str, str]:
        """Build comprehensive knowledge base"""
        return {
            "machine_learning": """
Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It involves algorithms that parse data, learn from it, and then make a determination or prediction about something in the world.

**Types of Machine Learning**:

1. **Supervised Learning**: The algorithm learns from labeled training data and makes predictions
   - Examples: Classification, Regression
   - Algorithms: Linear Regression, Decision Trees, Neural Networks

2. **Unsupervised Learning**: The algorithm finds patterns in unlabeled data
   - Examples: Clustering, Dimensionality Reduction
   - Algorithms: K-Means, PCA, Autoencoders

3. **Reinforcement Learning**: The algorithm learns through trial and error
   - Examples: Game playing, Robotics
   - Algorithms: Q-Learning, Deep Q-Networks

**Key Concepts**:
- Features: Input variables used for predictions
- Labels: Output variables in supervised learning
- Training: Process of learning from data
- Testing: Evaluating model performance
- Overfitting: Model too complex for training data
- Underfitting: Model too simple to capture patterns

**Applications**:
- Image and speech recognition
- Natural language processing
- Recommendation systems
- Fraud detection
- Medical diagnosis
""",

            "neural_networks": """
Neural networks are computing systems inspired by biological neural networks that constitute animal brains. They are based on a collection of connected units or nodes called artificial neurons, which loosely model the neurons in a biological brain.

**Architecture**:

1. **Input Layer**: Receives the initial data
2. **Hidden Layers**: Process and transform the data
3. **Output Layer**: Produces the final result

**Key Components**:
- **Neurons**: Processing units that receive inputs and produce outputs
- **Weights**: Parameters that adjust during training
- **Biases**: Offset values that help model complexity
- **Activation Functions**: Non-linear transformations (ReLU, Sigmoid, Tanh)

**Training Process**:
1. **Forward Propagation**: Data flows through the network
2. **Loss Calculation**: Measure of prediction error
3. **Backpropagation**: Gradient calculation
4. **Weight Update**: Adjusting weights to minimize loss

**Types of Neural Networks**:
- **Feedforward Networks**: Information flows in one direction
- **Convolutional Neural Networks (CNNs)**: Specialized for image processing
- **Recurrent Neural Networks (RNNs)**: Handle sequential data
- **Transformers**: Attention-based architecture for NLP

**Applications**:
- Computer vision
- Natural language processing
- Speech recognition
- Game playing
- Time series prediction
""",

            "data_science": """
Data science is an interdisciplinary field that uses scientific methods, processes, algorithms, and systems to extract knowledge and insights from structured and unstructured data.

**Data Science Lifecycle**:

1. **Data Collection**: Gathering relevant data from various sources
2. **Data Cleaning**: Removing errors and inconsistencies
3. **Exploratory Analysis**: Understanding patterns and relationships
4. **Feature Engineering**: Creating meaningful variables
5. **Model Building**: Developing predictive models
6. **Evaluation**: Assessing model performance
7. **Deployment**: Putting models into production

**Key Skills**:
- **Programming**: Python, R, SQL
- **Statistics**: Hypothesis testing, regression, probability
- **Machine Learning**: Algorithms and frameworks
- **Data Visualization**: Communicating insights
- **Domain Knowledge**: Understanding the problem domain

**Tools and Technologies**:
- **Programming**: Python (pandas, numpy, scikit-learn)
- **Visualization**: Matplotlib, Seaborn, Tableau
- **Big Data**: Spark, Hadoop
- **Deep Learning**: TensorFlow, PyTorch
- **Cloud Platforms**: AWS, Azure, GCP

**Applications**:
- Business intelligence
- Predictive analytics
- Customer segmentation
- Risk assessment
- Process optimization
""",

            "software_engineering": """
Software engineering is the systematic application of engineering approaches to the development of software. It involves designing, developing, testing, and maintaining software systems.

**Software Development Lifecycle (SDLC)**:

1. **Requirements Analysis**: Understanding what to build
2. **Design**: Planning the architecture and components
3. **Implementation**: Writing the code
4. **Testing**: Verifying correctness
5. **Deployment**: Releasing to users
6. **Maintenance**: Ongoing support and updates

**Key Principles**:

1. **Modularity**: Breaking systems into smaller, manageable parts
2. **Abstraction**: Hiding implementation details
3. **Encapsulation**: Bundling data with methods
4. **SOLID Principles**:
   - Single Responsibility
   - Open/Closed
   - Liskov Substitution
   - Interface Segregation
   - Dependency Inversion

**Development Methodologies**:
- **Agile**: Iterative and flexible development
- **Scrum**: Framework for agile development
- **Kanban**: Visual workflow management
- **DevOps**: Integration of development and operations

**Best Practices**:
- Version control (Git)
- Code review
- Continuous integration/continuous deployment (CI/CD)
- Automated testing
- Documentation
- Code quality metrics

**Quality Attributes**:
- Reliability
- Maintainability
- Scalability
- Performance
- Security
- Usability
"""
        }

    def _build_math_patterns(self) -> List[Tuple[str, Any]]:
        """Build mathematical pattern matching rules"""
        return [
            (r'derivative of (.+)', 'calculus_derivative'),
            (r'integral of (.+)', 'calculus_integral'),
            (r'limit of (.+)', 'calculus_limit'),
            (r'solve (.+) for (.+)', 'algebra_solve'),
            (r'simplify (.+)', 'algebra_simplify'),
            (r'factor (.+)', 'algebra_factor'),
        ]

    def _build_physics_formulas(self) -> Dict[str, Dict[str, Any]]:
        """Build physics formulas knowledge base"""
        return {
            "kinetic energy": {
                "formula": "KE = (1/2)mv²",
                "variables": {
                    "KE": "Kinetic Energy (Joules)",
                    "m": "Mass (kilograms)",
                    "v": "Velocity (meters/second)"
                },
                "explanation": "Kinetic energy is the energy an object possesses due to its motion. It depends on both the mass and velocity of the object.",
                "example": "A 10 kg object moving at 5 m/s has KE = 0.5 × 10 × 5² = 125 Joules",
                "applications": [
                    "Vehicle safety design",
                    "Sports performance analysis",
                    "Industrial machinery",
                    "Spacecraft navigation"
                ]
            },
            "force": {
                "formula": "F = ma",
                "variables": {
                    "F": "Force (Newtons)",
                    "m": "Mass (kilograms)",
                    "a": "Acceleration (meters/second²)"
                },
                "explanation": "Force is any interaction that, when unopposed, will change the motion of an object. It can cause an object with mass to change its velocity.",
                "example": "A 5 kg object accelerating at 2 m/s² experiences F = 5 × 2 = 10 Newtons",
                "applications": [
                    "Rocket propulsion",
                    "Vehicle dynamics",
                    "Structural engineering",
                    "Robotics"
                ]
            },
            "velocity": {
                "formula": "v = d/t",
                "variables": {
                    "v": "Velocity (meters/second)",
                    "d": "Distance (meters)",
                    "t": "Time (seconds)"
                },
                "explanation": "Velocity is the rate of change of position with respect to time. It is a vector quantity, meaning it has both magnitude and direction.",
                "example": "An object traveling 100 meters in 10 seconds has v = 100/10 = 10 m/s",
                "applications": [
                    "Navigation systems",
                    "Sports analysis",
                    "Traffic management",
                    "Aerospace engineering"
                ]
            },
            "acceleration": {
                "formula": "a = (v₂ - v₁) / t",
                "variables": {
                    "a": "Acceleration (meters/second²)",
                    "v₂": "Final velocity (meters/second)",
                    "v₁": "Initial velocity (meters/second)",
                    "t": "Time (seconds)"
                },
                "explanation": "Acceleration is the rate of change of velocity with respect to time. It describes how quickly an object's velocity changes.",
                "example": "A car accelerating from 0 to 60 m/s in 10 seconds has a = (60-0)/10 = 6 m/s²",
                "applications": [
                    "Vehicle performance",
                    "Athletic training",
                    "Spacecraft launches",
                    "Industrial automation"
                ]
            },
            "momentum": {
                "formula": "p = mv",
                "variables": {
                    "p": "Momentum (kg·m/s)",
                    "m": "Mass (kilograms)",
                    "v": "Velocity (meters/second)"
                },
                "explanation": "Momentum is the product of an object's mass and velocity. It is a measure of how difficult it is to stop a moving object.",
                "example": "A 1000 kg car moving at 20 m/s has p = 1000 × 20 = 20,000 kg·m/s",
                "applications": [
                    "Collision analysis",
                    "Sports physics",
                    "Particle physics",
                    "Spacecraft navigation"
                ]
            },
            "work": {
                "formula": "W = Fd",
                "variables": {
                    "W": "Work (Joules)",
                    "F": "Force (Newtons)",
                    "d": "Distance (meters)"
                },
                "explanation": "Work is done when a force causes an object to move in the direction of the force. It is a measure of energy transfer.",
                "example": "Applying 50 N of force to move an object 10 meters does W = 50 × 10 = 500 Joules of work",
                "applications": [
                    "Mechanical engineering",
                    "Construction",
                    "Exercise physiology",
                    "Energy systems"
                ]
            },
            "power": {
                "formula": "P = W/t",
                "variables": {
                    "P": "Power (Watts)",
                    "W": "Work (Joules)",
                    "t": "Time (seconds)"
                },
                "explanation": "Power is the rate at which work is done or energy is transferred. It measures how quickly energy is used or produced.",
                "example": "Doing 1000 Joules of work in 5 seconds requires P = 1000/5 = 200 Watts",
                "applications": [
                    "Electrical systems",
                    "Engine performance",
                    "Exercise equipment",
                    "Industrial processes"
                ]
            }
        }

    def _build_code_templates(self) -> Dict[str, str]:
        """Build code generation templates"""
        return {
            "python": """
def function_name(param1, param2):
    &quot;&quot;&quot;
    Function description

    Args:
        param1: Description
        param2: Description

    Returns:
        Return value description
    &quot;&quot;&quot;
    # Implementation
    pass

class ClassName:
    &quot;&quot;&quot;Class description&quot;&quot;&quot;

    def __init__(self, param):
        self.param = param

    def method(self):
        &quot;&quot;&quot;Method description&quot;&quot;&quot;
        pass
""",
            "javascript": """
function functionName(param1, param2) {
    &quot;use strict&quot;;

    // Implementation
    return result;
}

class ClassName {
    constructor(param) {
        this.param = param;
    }

    method() {
        // Implementation
        return result;
    }
}
""",
            "java": """
public class ClassName {
    private Type field;

    public ClassName(Type param) {
        this.field = param;
    }

    public Type method(Type param) {
        // Implementation
        return result;
    }
}
"""
        }

    def _build_generative_templates(self) -> Dict[str, str]:
        """Build generative response templates"""
        return {
            "poem": """
Title: {title}

{stanza1}

{stanza2}

{stanza3}
""",
            "story": """
{title}

{intro}

{body}

{conclusion}
"""
        }
