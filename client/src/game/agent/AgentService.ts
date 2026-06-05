import Scenario from "@/game/Scenario";
import Aircraft from "@/game/units/Aircraft";
import { SIDE_COLOR } from "@/utils/colors";

export type AgentConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "error";

export interface AgentDestination {
  latitude: number;
  longitude: number;
}

export interface AgentAction {
  requestId: string;
  aircraftId: string;
  action: [number, number];
  destination: AgentDestination;
}

interface AgentResponse {
  requestId?: string;
  aircraftId?: string;
  action?: number[];
  destination?: AgentDestination;
  error?: string;
}

interface PendingRequest {
  resolve: (action: AgentAction) => void;
  reject: (error: Error) => void;
  timeoutId: number;
}

const TRAINING_AIRCRAFT_NAME = "Blue Trainee";
const REQUEST_TIMEOUT_MS = 5000;

export default class AgentService {
  private ws: WebSocket | null = null;
  private pendingRequests = new Map<string, PendingRequest>();
  status: AgentConnectionStatus = "disconnected";

  connect(url: string): Promise<void> {
    this.disconnect();
    this.status = "connecting";

    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      this.ws = ws;

      ws.onopen = () => {
        this.status = "connected";
        resolve();
      };

      ws.onerror = () => {
        this.status = "error";
        reject(new Error(`Failed to connect to AI Agent at ${url}`));
      };

      ws.onclose = () => {
        this.status = "disconnected";
        this.rejectPendingRequests("AI Agent connection closed.");
      };

      ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };
    });
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.status = "disconnected";
    this.rejectPendingRequests("AI Agent disconnected.");
  }

  requestAction(observation: number[], aircraftId: string): Promise<AgentAction> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("AI Agent is not connected."));
    }

    const requestId = crypto.randomUUID();
    const payload = {
      requestId,
      aircraftId,
      observation,
    };

    return new Promise((resolve, reject) => {
      const timeoutId = window.setTimeout(() => {
        this.pendingRequests.delete(requestId);
        reject(new Error("AI Agent request timed out."));
      }, REQUEST_TIMEOUT_MS);

      this.pendingRequests.set(requestId, { resolve, reject, timeoutId });
      this.ws?.send(JSON.stringify(payload));
    });
  }

  extractObservation(scenario: Scenario): {
    aircraft: Aircraft;
    observation: number[];
  } | null {
    const aircraft = this.getTrainingAircraft(scenario);
    if (!aircraft) return null;

    return {
      aircraft,
      observation: [aircraft.latitude, aircraft.longitude],
    };
  }

  private getTrainingAircraft(scenario: Scenario): Aircraft | undefined {
    const namedAircraft = scenario.aircraft.find(
      (aircraft) => aircraft.name === TRAINING_AIRCRAFT_NAME
    );
    if (namedAircraft) return namedAircraft;

    const blueAircraft = scenario.aircraft.find(
      (aircraft) => aircraft.sideColor === SIDE_COLOR.BLUE
    );
    if (blueAircraft) return blueAircraft;

    return scenario.aircraft[0];
  }

  private handleMessage(rawMessage: string): void {
    let response: AgentResponse;
    try {
      response = JSON.parse(rawMessage);
    } catch {
      return;
    }

    const requestId = response.requestId;
    if (!requestId) return;

    const pendingRequest = this.pendingRequests.get(requestId);
    if (!pendingRequest) return;

    window.clearTimeout(pendingRequest.timeoutId);
    this.pendingRequests.delete(requestId);

    if (response.error) {
      pendingRequest.reject(new Error(response.error));
      return;
    }

    if (
      !response.aircraftId ||
      !response.action ||
      response.action.length !== 2 ||
      !response.destination
    ) {
      pendingRequest.reject(new Error("AI Agent returned an invalid response."));
      return;
    }

    pendingRequest.resolve({
      requestId,
      aircraftId: response.aircraftId,
      action: [response.action[0], response.action[1]],
      destination: response.destination,
    });
  }

  private rejectPendingRequests(message: string): void {
    this.pendingRequests.forEach((pendingRequest) => {
      window.clearTimeout(pendingRequest.timeoutId);
      pendingRequest.reject(new Error(message));
    });
    this.pendingRequests.clear();
  }
}
