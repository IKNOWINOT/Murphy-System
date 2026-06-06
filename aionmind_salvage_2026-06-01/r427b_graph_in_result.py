# Extracted from runtime_kernel.py 2026-06-01
# R427B: include graph + node states in kernel result envelope

            "graph_id": graph.graph_id,
                "status": "pending_approval",
                "auto_approved": False,
                "graph": graph.model_dump(),
                "note": "Graph requires human approval before execution.",
            }
            self._append_audit_log(result, actor=actor, task_type=task_type)
            return result

        # Step 5 — execute
        state = self.execute(graph, actor=actor)

        # Step 6 — memory archival
        self._memory.store_intermediate_state(
            f"pipeline:{state.execution_id}",
            {
                "context_id": ctx.context_id,
                "graph_id": graph.graph_id,
                "execution_id": state.execution_id,
                "status": state.status.value,
                "task_type": task_type,
                "raw_input": raw_input,
            },
        )

        status_val = state.status.value
        if status_val == "completed":
            self._aionmind_metrics["executed"] += 1
        elif status_val == "failed":
            self._aionmind_metrics["failed"] += 1

        result = {
            "pipeline": "aionmind",
            "context_id": ctx.context_id,
            "graph_id": graph.graph_id,
            "execution_id": state.execution_id,
            "status": status_val,
            "auto_approved": auto_approved_now,
            # _R427B_GRAPH_IN_RESULT — include graph + state for UI rendering
            "graph": graph.model_dump(),
            "state": {
                "execution_id": state.execution_id,
                "status": state.status.value,
                "node_states": [
                    {
                        "node_id": ns.node_id,
                        "status": ns.status.value if hasattr(ns.status, "value") else str(ns.status),
                        "started_at": getattr(ns, "started_at", None),
                        "completed_at": getattr(ns, "completed_at", None),
                        "error": getattr(ns, "error", None),
                    }
                    for ns in (getattr(state, "node_states", []) or [])
                ],
            },