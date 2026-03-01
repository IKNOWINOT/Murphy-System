import { DurableObject } from 'cloudflare:workers';

interface AgentState {
  agentId: string;
  ownerId: string;
  status: string;
  assignments: Record<string, unknown>[];
  lastUpdated: string;
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * ShadowAgentState Durable Object.
 * Manages stateful shadow agent sessions and assignment tracking.
 */
export class ShadowAgentState extends DurableObject {
  private state: AgentState | null = null;

  private async loadState(): Promise<AgentState | null> {
    if (!this.state) {
      this.state = await this.ctx.storage.get<AgentState>('state') ?? null;
    }
    return this.state;
  }

  private async saveState(): Promise<void> {
    if (this.state) {
      await this.ctx.storage.put('state', this.state);
    }
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/init' && request.method === 'POST') {
      return this.handleInit(request);
    }
    if (path === '/status' && request.method === 'GET') {
      return this.handleStatus();
    }
    if (path === '/update' && request.method === 'POST') {
      return this.handleUpdate(request);
    }
    if (path === '/assign' && request.method === 'POST') {
      return this.handleAssign(request);
    }

    return jsonResponse({ error: 'Not found' }, 404);
  }

  private async handleInit(request: Request): Promise<Response> {
    const body = await request.json() as {
      agentId: string;
      ownerId: string;
    };

    this.state = {
      agentId: body.agentId,
      ownerId: body.ownerId,
      status: 'idle',
      assignments: [],
      lastUpdated: new Date().toISOString(),
    };

    await this.saveState();
    return jsonResponse({ initialized: true, state: this.state });
  }

  private async handleStatus(): Promise<Response> {
    const state = await this.loadState();
    if (!state) {
      return jsonResponse({ error: 'Agent not initialized' }, 400);
    }
    return jsonResponse({ state });
  }

  private async handleUpdate(request: Request): Promise<Response> {
    const state = await this.loadState();
    if (!state) {
      return jsonResponse({ error: 'Agent not initialized' }, 400);
    }

    const body = await request.json() as { status?: string };
    if (body.status) {
      state.status = body.status;
    }
    state.lastUpdated = new Date().toISOString();
    await this.saveState();

    return jsonResponse({ updated: true, state });
  }

  private async handleAssign(request: Request): Promise<Response> {
    const state = await this.loadState();
    if (!state) {
      return jsonResponse({ error: 'Agent not initialized' }, 400);
    }

    const body = await request.json() as { assignment: Record<string, unknown> };
    state.assignments.push(body.assignment);
    state.status = 'active';
    state.lastUpdated = new Date().toISOString();
    await this.saveState();

    return jsonResponse({ assigned: true, state });
  }
}
