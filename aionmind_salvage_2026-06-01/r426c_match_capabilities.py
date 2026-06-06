# Extracted from reasoning_engine.py 2026-06-01
# Contains R426B_ALLOWLIST_FILTER + R426C_PERMISSIVE_FILTER

    def _match_capabilities(self, context: ContextObject) -> List[Capability]:
        """Find capabilities relevant to *context*, filtered by Rosetta role.

        _R426B_ALLOWLIST_FILTER:
          R426 injects task_config into context.metadata. If present, we
          treat the role's capability_allowlist as the universe of
          permitted endpoint groups. Capabilities outside the allowlist
          are invisible to candidate generation — the reasoning engine
          literally cannot plan over what the role isn't allowed to touch.
        """
        # Simple heuristic: match on intent keywords as tags
        tags = [t.strip().lower() for t in context.intent.split() if t.strip()]
        if tags:
            results = self._registry.search(tags=tags)
        else:
            results = self._registry.list_all()
        if not results:
            results = self._registry.list_all()

        # _R426C_PERMISSIVE_FILTER — Rosetta allowlist + handler check
        # If intent-tag search returned nothing, search the full registry
        # constrained by the role allowlist. This avoids the empty-plan
        # failure mode when chat phrasing doesn't match cap tags.
        try:
            task_cfg = (context.metadata or {}).get("task_config") or {}
            allowlist = task_cfg.get("capability_allowlist") or []
            allow_set = {str(g).lower() for g in allowlist} if allowlist else set()

            # Get handler map once (R424 attached handlers here)
            handlers = getattr(self._registry, "_handlers", {}) or {}

            def _cap_group(c):
                md = getattr(c, "metadata", {}) or {}
                g = str(md.get("group") or "").lower()
                if g:
                    return g
                for t in (getattr(c, "tags", []) or []):
                    tl = str(t).lower()
                    if tl in allow_set:
                        return tl
                return ""

            def _is_runnable(c):
                cap_id = getattr(c, "capability_id", "")
                if cap_id in handlers:
                    return True
                md = getattr(c, "metadata", {}) or {}
                # Allow caps with origin=r424_endpoint_bridge — they self-bind
                if md.get("origin") == "r424_endpoint_bridge":
                    return True
                # Drop bot_inv:* and other handler-less stubs
                if cap_id.startswith(("bot_inv:", "stub:", "todo:")):
                    return False
                return True

            # Source pool: if tag-search was thin (< 5 results) or empty,
            # widen to full registry for the allowlist filter.
            if len(results) < 5:
                pool = self._registry.list_all()
            else:
                pool = results

            filtered = []
            for c in pool:
                if not _is_runnable(c):
                    continue
                if allow_set:
                    g = _cap_group(c)
                    if not g or g not in allow_set:
                        continue
                filtered.append(c)

            # Cap to 50 candidates to keep planning fast
            if len(filtered) > 50:
                filtered = filtered[:50]

            # If allowlist is set and filter wipes everything, return empty
            # (tenant boundary: better to refuse than leak)
            if allow_set:
                return filtered
            # Otherwise return filtered (still drops bot_inv stubs)
            return filtered if filtered else results
        except Exception:
            return results
