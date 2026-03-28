"""
Task Executor - Executes tasks using available tools
Reading level: High school student
"""
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger("task_executor")

class TaskExecutor:
    """
    Executes tasks using the tools and modules that are available
    Automatically selects the best way to do something
    """

    def __init__(self):
        # Available tools (will be populated by modules)
        self.tools: Dict[str, Callable] = {}

        # Task history
        self.task_history: List[Dict[str, Any]] = []

        # Performance metrics
        self.metrics = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "average_time": 0.0
        }

    def register_tool(self, name: str, tool: Callable,
                     description: str, capabilities: List[str]):
        """
        Register a tool that can execute tasks

        Args:
            name: Name of the tool
            tool: Function that performs the tool's action
            description: What the tool does
            capabilities: List of things the tool can do
        """
        self.tools[name] = {
            "function": tool,
            "description": description,
            "capabilities": capabilities
        }

    def select_best_tool(self, task_description: str,
                        required_capabilities: List[str]) -> Optional[str]:
        """
        Automatically select the best tool for a task

        Args:
            task_description: What needs to be done
            required_capabilities: What the tool needs to be able to do

        Returns:
            Name of the best tool, or None if no suitable tool found
        """
        best_tool = None
        best_match_score = 0

        # Score each tool based on how well it matches requirements
        for tool_name, tool_info in self.tools.items():
            match_score = self._calculate_match_score(
                tool_info,
                task_description,
                required_capabilities
            )

            if match_score > best_match_score:
                best_match_score = match_score
                best_tool = tool_name

        return best_tool if best_match_score > 0 else None

    def _calculate_match_score(self, tool_info: Dict[str, Any],
                              task_description: str,
                              required_capabilities: List[str]) -> float:
        """
        Calculate how well a tool matches the requirements

        Returns a score between 0.0 and 1.0
        """
        score = 0.0

        # Check if tool has required capabilities
        tool_capabilities = tool_info.get("capabilities", [])
        capability_matches = 0
        for req_cap in required_capabilities:
            if req_cap in tool_capabilities:
                capability_matches += 1

        # Capability match score (0.5 of total)
        if required_capabilities:
            capability_score = capability_matches / (len(required_capabilities) or 1)
            score += capability_score * 0.5

        # Description keyword match (0.3 of total)
        tool_desc = tool_info.get("description", "").lower()
        task_desc = task_description.lower()

        # Simple keyword matching
        task_words = set(task_desc.split())
        desc_words = set(tool_desc.split())

        word_matches = len(task_words & desc_words)
        if task_words:
            keyword_score = word_matches / (len(task_words) or 1)
            score += keyword_score * 0.3

        # Tool availability (0.2 of total)
        # All tools in self.tools are available
        score += 0.2

        return score

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task using the best available tool

        Args:
            task: Task specification with:
                - description: What needs to be done
                - required_capabilities: What the tool needs to do
                - parameters: Any parameters for the task
                - timeout: How long to wait (optional)

        Returns:
            Result of the task execution
        """
        start_time = time.time()

        # Select the best tool
        best_tool = self.select_best_tool(
            task.get("description", ""),
            task.get("required_capabilities", [])
        )

        if best_tool is None:
            result = {
                "success": False,
                "error": "No suitable tool found for this task",
                "task": task
            }
            self._record_task(result, start_time)
            return result

        # Execute the task with the selected tool
        try:
            tool_info = self.tools[best_tool]
            tool_function = tool_info["function"]

            # Execute with timeout if specified
            timeout = task.get("timeout", None)
            parameters = task.get("parameters", {})

            if timeout:
                # Simple timeout implementation
                result = self._execute_with_timeout(
                    tool_function,
                    parameters,
                    timeout
                )
            else:
                result = tool_function(**parameters)

            # Record success
            self._record_task({
                "success": True,
                "tool_used": best_tool,
                "result": result,
                "task": task
            }, start_time)

            return {
                "success": True,
                "tool_used": best_tool,
                "result": result
            }

        except Exception as exc:
            # Record failure
            logger.debug("Caught exception: %s", exc)
            self._record_task({
                "success": False,
                "tool_used": best_tool,
                "error": str(exc),
                "task": task
            }, start_time)

            return {
                "success": False,
                "tool_used": best_tool,
                "error": str(exc)
            }

    def _execute_with_timeout(self, func: Callable, parameters: Dict,
                             timeout: float) -> Any:
        """Execute a function with a timeout using ThreadPoolExecutor.

        Uses concurrent.futures instead of signal.SIGALRM so that this works
        on Windows and from non-main threads (e.g. ASGI workers).
        """
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, **parameters)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"Task timed out after {timeout} seconds")

    def _record_task(self, result: Dict[str, Any], start_time: float):
        """Record task execution for metrics"""
        execution_time = time.time() - start_time

        self.metrics["total_tasks"] += 1
        if result.get("success", False):
            self.metrics["successful_tasks"] += 1
        else:
            self.metrics["failed_tasks"] += 1

        # Update average time
        total_time = self.metrics["average_time"] * (self.metrics["total_tasks"] - 1)
        self.metrics["average_time"] = (total_time + execution_time) / self.metrics["total_tasks"]

        # Add to history
        task_record = {
            "timestamp": time.time(),
            "execution_time": execution_time,
            **result
        }
        capped_append(self.task_history, task_record, max_size=100)

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            **self.metrics,
            "success_rate": (
                self.metrics["successful_tasks"] / self.metrics["total_tasks"]
                if self.metrics["total_tasks"] > 0 else 0.0
            ),
            "available_tools": len(self.tools)
        }

    def get_task_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent task history"""
        return self.task_history[-limit:]

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools"""
        tools_list = []
        for name, info in self.tools.items():
            tools_list.append({
                "name": name,
                "description": info["description"],
                "capabilities": info["capabilities"]
            })
        return tools_list

# Initialize for easy import
task_executor = TaskExecutor()

if __name__ == "__main__":
    logger.info("Task Executor Module")
    logger.info("Executes tasks using available tools")
