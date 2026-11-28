// engine/src/entry.js: the server the agent's tool calls reach, driven in this process over an in-memory MCP
// connection. Its tools are exactly the pinned contract (engine/contract/tools.json, which the plugin and Hermes rely
// on), and arguments a tool does not take are refused as a tool error, with the server still answering.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

import { createGbStudioServer } from "../../engine/src/entry.js";

const CONTRACT = JSON.parse(await readFile(new URL("../../engine/contract/tools.json", import.meta.url), "utf8"));
const FIELDS = ["title", "description", "inputSchema", "outputSchema", "annotations", "execution"];

async function connected(t) {
  const { server, close } = createGbStudioServer();
  const [serverSide, clientSide] = InMemoryTransport.createLinkedPair();
  await server.connect(serverSide);
  const client = new Client({ name: "hermretro-engine-test", version: "1" });
  await client.connect(clientSide);
  t.after(async () => {
    await client.close();
    await close();
  });
  return client;
}

test("the server names itself and lists exactly the pinned tools, field by field", async (t) => {
  const client = await connected(t);
  const { name, title } = client.getServerVersion();
  assert.deepEqual({ name, title }, CONTRACT.initialize.serverInfo);
  const { tools } = await client.listTools();
  assert.deepEqual(
    tools.map((tool) => tool.name),
    CONTRACT.tools.map((tool) => tool.name),
    "the same tools in the same order (FIX: python tools/engine/reconcile_schemas.py engine/contract/tools.json)",
  );
  const pinned = new Map(CONTRACT.tools.map((tool) => [tool.name, tool]));
  for (const tool of tools) {
    for (const field of FIELDS) {
      assert.deepEqual(tool[field], pinned.get(tool.name)[field], `${tool.name}'s ${field} is the pinned one`);
    }
  }
});

test("arguments a tool does not take are a tool error, and the server goes on answering", async (t) => {
  const client = await connected(t);
  const refused = await client.callTool({ name: "project_inventory", arguments: { projectPath: 42 } });
  assert.equal(refused.isError, true);
  assert.match(refused.content[0].text, /Invalid arguments for tool project_inventory/);
  const { tools } = await client.listTools();
  assert.equal(tools.length, CONTRACT.tools.length);
});
