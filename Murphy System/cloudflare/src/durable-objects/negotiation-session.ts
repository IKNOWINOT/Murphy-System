import { DurableObject } from 'cloudflare:workers';

interface NegotiationState {
  negotiationId: string;
  initiatorOrgId: string;
  responderOrgId: string;
  rounds: NegotiationRound[];
  status: string;
  fairnessThreshold: number;
}

interface NegotiationRound {
  round: number;
  proposer: string;
  offered: number;
  requested: number;
  timestamp: string;
}

interface FairnessScore {
  G: number;
  D: number;
  H: number;
  combined: number;
  recommendation: string;
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * NegotiationSession Durable Object.
 * Manages stateful inter-org negotiations with Murphy fairness scoring.
 */
export class NegotiationSession extends DurableObject {
  private state: NegotiationState | null = null;

  private async loadState(): Promise<NegotiationState | null> {
    if (!this.state) {
      this.state = await this.ctx.storage.get<NegotiationState>('state') ?? null;
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

    if (path === '/propose' && request.method === 'POST') {
      return this.handlePropose(request);
    }
    if (path === '/counter' && request.method === 'POST') {
      return this.handleCounter(request);
    }
    if (path === '/evaluate' && request.method === 'GET') {
      return this.handleEvaluate();
    }
    if (path === '/accept' && request.method === 'POST') {
      return this.handleAccept(request);
    }
    if (path === '/reject' && request.method === 'POST') {
      return this.handleReject(request);
    }
    if (path === '/status' && request.method === 'GET') {
      return this.handleStatus();
    }

    return jsonResponse({ error: 'Not found' }, 404);
  }

  private async handlePropose(request: Request): Promise<Response> {
    const body = await request.json() as {
      negotiationId: string;
      initiatorOrgId: string;
      responderOrgId: string;
      proposal: { offered: number; requested: number };
      fairnessThreshold: number;
    };

    this.state = {
      negotiationId: body.negotiationId,
      initiatorOrgId: body.initiatorOrgId,
      responderOrgId: body.responderOrgId,
      rounds: [{
        round: 1,
        proposer: body.initiatorOrgId,
        offered: body.proposal.offered,
        requested: body.proposal.requested,
        timestamp: new Date().toISOString(),
      }],
      status: 'proposed',
      fairnessThreshold: body.fairnessThreshold,
    };

    await this.saveState();

    const fairness = this.computeFairness();
    return jsonResponse({ state: this.state, fairness });
  }

  private async handleCounter(request: Request): Promise<Response> {
    const state = await this.loadState();
    if (!state) {
      return jsonResponse({ error: 'No active negotiation' }, 400);
    }

    const body = await request.json() as {
      orgId: string;
      offered: number;
      requested: number;
      fairnessThreshold?: number;
    };

    const round: NegotiationRound = {
      round: state.rounds.length + 1,
      proposer: body.orgId,
      offered: body.offered,
      requested: body.requested,
      timestamp: new Date().toISOString(),
    };

    state.rounds.push(round);
    state.status = 'active';
    if (body.fairnessThreshold !== undefined) {
      state.fairnessThreshold = body.fairnessThreshold;
    }
    await this.saveState();

    const fairness = this.computeFairness();
    return jsonResponse({ state, fairness });
  }

  private async handleEvaluate(): Promise<Response> {
    const state = await this.loadState();
    if (!state) {
      return jsonResponse({ error: 'No active negotiation' }, 400);
    }
    const fairness = this.computeFairness();
    return jsonResponse({ fairness, rounds: state.rounds });
  }

  private async handleAccept(request: Request): Promise<Response> {
    const state = await this.loadState();
    if (!state) {
      return jsonResponse({ error: 'No active negotiation' }, 400);
    }
    state.status = 'accepted';
    await this.saveState();
    return jsonResponse({ status: 'accepted', rounds: state.rounds.length });
  }

  private async handleReject(request: Request): Promise<Response> {
    const state = await this.loadState();
    if (!state) {
      return jsonResponse({ error: 'No active negotiation' }, 400);
    }
    state.status = 'rejected';
    await this.saveState();
    return jsonResponse({ status: 'rejected', rounds: state.rounds.length });
  }

  private async handleStatus(): Promise<Response> {
    const state = await this.loadState();
    if (!state) {
      return jsonResponse({ error: 'No active negotiation' }, 400);
    }
    const fairness = this.computeFairness();
    return jsonResponse({ state, fairness });
  }

  /**
   * Murphy G/D/H fairness scoring.
   * G(x) = balance of value exchange: 1 - |offered - requested| / total
   * D(x) = trend toward fairness over rounds
   * H(x) = risk asymmetry: 1 - min(offered,requested)/max(offered,requested)
   * Combined: w_g(0.4)*G + w_d(0.4)*D - kappa(0.3)*H, clamped [0,1]
   */
  private computeFairness(): FairnessScore {
    if (!this.state || this.state.rounds.length === 0) {
      return { G: 0, D: 0, H: 0, combined: 0, recommendation: 'no_data' };
    }

    const latest = this.state.rounds[this.state.rounds.length - 1];
    const total = latest.offered + latest.requested;

    // G(x) — balance of value exchange
    const G = total > 0 ? 1 - Math.abs(latest.offered - latest.requested) / total : 0;

    // D(x) — trend toward fairness over rounds
    let D = 0.5; // neutral default
    if (this.state.rounds.length >= 2) {
      const prev = this.state.rounds[this.state.rounds.length - 2];
      const prevTotal = prev.offered + prev.requested;
      const prevG = prevTotal > 0 ? 1 - Math.abs(prev.offered - prev.requested) / prevTotal : 0;
      D = G > prevG ? Math.min(1, 0.5 + (G - prevG)) : Math.max(0, 0.5 - (prevG - G));
    }

    // H(x) — risk asymmetry
    const maxVal = Math.max(latest.offered, latest.requested);
    const minVal = Math.min(latest.offered, latest.requested);
    const H = maxVal > 0 ? 1 - minVal / maxVal : 0;

    // Combined: w_g * G + w_d * D - kappa * H
    const wG = 0.4;
    const wD = 0.4;
    const kappa = 0.3;
    const combined = Math.max(0, Math.min(1, wG * G + wD * D - kappa * H));

    let recommendation: string;
    if (combined >= this.state.fairnessThreshold) {
      recommendation = 'recommend_accept';
    } else if (combined <= 0.4) {
      recommendation = 'escalate_to_human';
    } else {
      recommendation = 'continue_negotiation';
    }

    return { G: Math.round(G * 1000) / 1000, D: Math.round(D * 1000) / 1000, H: Math.round(H * 1000) / 1000, combined: Math.round(combined * 1000) / 1000, recommendation };
  }
}
