// Loads the engine's packages for its tests (resolve.mjs): node --import ./tests/engine/register.mjs --test ...
import * as nodeModule from "node:module";

import { resolve } from "./resolve.mjs";

if (nodeModule.registerHooks) nodeModule.registerHooks({ resolve });
else nodeModule.register("./resolve.mjs", import.meta.url); // Node 22 before 22.15
