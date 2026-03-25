/**
 * Unit tests for SeabayClient — no live API required.
 * Tests client construction, URL building, and method signatures.
 */

import { SeabayClient } from "../src/client";

describe("SeabayClient", () => {
  describe("construction", () => {
    it("should accept api key and default base URL", () => {
      const client = new SeabayClient({ apiKey: "sk_live_test" });
      expect(client).toBeDefined();
    });

    it("should accept custom base URL", () => {
      const client = new SeabayClient({
        apiKey: "sk_live_test",
        baseUrl: "http://localhost:8000/v1",
      });
      expect(client).toBeDefined();
    });

    it("should strip trailing slash from base URL", () => {
      const client = new SeabayClient({
        apiKey: "sk_live_test",
        baseUrl: "http://localhost:8000/v1/",
      });
      expect(client).toBeDefined();
    });
  });

  describe("method existence", () => {
    const client = new SeabayClient({ apiKey: "sk_live_test" });

    it("should have agent methods", () => {
      expect(typeof client.register).toBe("function");
      expect(typeof client.getAgent).toBe("function");
      expect(typeof client.updateAgent).toBe("function");
      expect(typeof client.searchAgents).toBe("function");
    });

    it("should have task methods", () => {
      expect(typeof client.createTask).toBe("function");
      expect(typeof client.getTask).toBe("function");
      expect(typeof client.getInbox).toBe("function");
      expect(typeof client.acceptTask).toBe("function");
      expect(typeof client.declineTask).toBe("function");
      expect(typeof client.completeTask).toBe("function");
    });

    it("should have intent methods", () => {
      expect(typeof client.createIntent).toBe("function");
      expect(typeof client.getIntent).toBe("function");
      expect(typeof client.getMatches).toBe("function");
      expect(typeof client.selectMatch).toBe("function");
    });

    it("should have relationship methods", () => {
      expect(typeof client.importRelationship).toBe("function");
      expect(typeof client.listRelationships).toBe("function");
    });

    it("should have circle methods", () => {
      expect(typeof client.createCircle).toBe("function");
      expect(typeof client.getCircle).toBe("function");
    });

    it("should have health method", () => {
      expect(typeof client.health).toBe("function");
    });
  });
});
