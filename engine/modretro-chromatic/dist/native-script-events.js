/**
 * Native ScriptValue forms accepted by GB Studio 4.3.x.
 *
 * This module deliberately has no runtime dependency on project authoring or
 * upstream source: every mutation boundary must be able to share it without
 * creating an import cycle or requiring an optional vendor checkout.
 */
import { unbuildableEventMessage } from "./event-catalog.js";
import { stableResourceId } from "./project-files.js";
export const SCRIPT_KEYS = /^(?:script|[A-Za-z][A-Za-z0-9]*Script)$/;
const ACTOR_PROPERTIES = new Set([
    "xpos", "ypos", "pxpos", "pypos", "direction", "frame",
    "xdeadzone", "ydeadzone", "xoffset", "yoffset", "xscroll", "yscroll",
]);
const BINARY_OPERATORS = new Set([
    "add", "sub", "mul", "div", "mod", "min", "max",
    "eq", "ne", "gt", "gte", "lt", "lte", "and", "or", "atan2",
    "shl", "shr", "bAND", "bOR", "bXOR",
]);
const UNARY_OPERATORS = new Set(["rnd", "not", "isqrt", "abs", "neg", "bNOT"]);
const MAXIMUM_SCRIPT_VALUE_DEPTH = 64;
export const MAXIMUM_EVENT_DEPTH = 64;
const MAXIMUM_EVENT_COUNT = 10_000;
const TYPED_EVENT_ARGUMENTS = new Map([
    ["EVENT_SWITCH_SCENE", ["x", "y"]],
    ["EVENT_ACTOR_SET_DIRECTION", ["direction"]],
    ["EVENT_IF_ACTOR_DIRECTION", ["direction"]],
    ["EVENT_ACTOR_SET_POSITION", ["x", "y"]],
    ["EVENT_ACTOR_SET_POSITION_RELATIVE", ["x", "y"]],
    ["EVENT_ACTOR_MOVE_TO", ["x", "y"]],
    ["EVENT_ACTOR_MOVE_RELATIVE", ["x", "y"]],
    ["EVENT_IF_ACTOR_AT_POSITION", ["x", "y"]],
]);
const REQUIRED_EVENT_ARGUMENTS = new Set(["direction"]);
const SCRIPT_DIRECTIONS = new Set(["up", "down", "left", "right"]);
export function isObject(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
/** Match upstream's deliberately permissive `isScriptValue` contract. */
export function isNativeScriptValue(value, depth = 0) {
    if (depth > MAXIMUM_SCRIPT_VALUE_DEPTH || !isObject(value))
        return false;
    const type = value.type;
    if (typeof type !== "string")
        return false;
    switch (type) {
        case "number":
            return typeof value.value === "number";
        case "numberSymbol":
        case "direction":
        case "variable":
        case "constant":
        case "expression":
        case "engineField":
            return typeof value.value === "string";
        case "property":
            return typeof value.target === "string"
                && typeof value.property === "string"
                && ACTOR_PROPERTIES.has(value.property);
        case "true":
        case "false":
        case "indirect":
            return true;
        default:
            if (BINARY_OPERATORS.has(type)) {
                return (!value.valueA || isNativeScriptValue(value.valueA, depth + 1))
                    && (!value.valueB || isNativeScriptValue(value.valueB, depth + 1));
            }
            if (UNARY_OPERATORS.has(type)) {
                return !value.value || isNativeScriptValue(value.value, depth + 1);
            }
            return false;
    }
}
function indexScriptEvents(resource, strict = false) {
    const indexed = new Map();
    const orderedEvents = [];
    if (!resource)
        return { events: indexed, orderedEvents };
    let count = 0;
    let error;
    function visit(events, depth) {
        if (error)
            return;
        if (depth > MAXIMUM_EVENT_DEPTH) {
            if (strict) {
                error = { eventId: "unknown", message: "Script event tree exceeds the maximum nesting depth" };
            }
            return;
        }
        for (const event of events) {
            if (error)
                return;
            if (++count > MAXIMUM_EVENT_COUNT) {
                if (strict) {
                    error = { eventId: "unknown", message: "Script event tree exceeds the maximum event count" };
                }
                return;
            }
            if (!isObject(event))
                continue;
            orderedEvents.push(event);
            if (typeof event.id === "string" && !indexed.has(event.id))
                indexed.set(event.id, event);
            if (!isObject(event.children))
                continue;
            for (const branch of Object.values(event.children)) {
                if (Array.isArray(branch))
                    visit(branch, depth + 1);
            }
        }
    }
    for (const [key, events] of Object.entries(resource)) {
        if (SCRIPT_KEYS.test(key) && Array.isArray(events))
            visit(events, 0);
    }
    return { events: indexed, orderedEvents, ...(error ? { error } : {}) };
}
// The events a request writes, each with the arguments it gives: they are checked again even when unchanged.
export function explicitlyPatchedNativeScriptValues(patch) {
    const patched = new Map();
    for (const event of indexScriptEvents(patch).orderedEvents) {
        const eventId = typeof event.id === "string" && event.id ? event.id : "unknown";
        const values = patched.get(eventId) ?? new Set();
        for (const key of isObject(event.args) ? Object.keys(event.args) : [])
            values.add(key);
        patched.set(eventId, values);
    }
    return patched;
}
export function assignNativeScriptEventIds(resource) {
    const taken = new Set(indexScriptEvents(resource).events.keys());
    const ownerId = typeof resource.id === "string" && resource.id ? resource.id : "resource";
    function assign(events, location, depth) {
        if (depth > MAXIMUM_EVENT_DEPTH)
            return;
        events.forEach((event, index) => {
            if (!isObject(event))
                return;
            const position = `${location}/${index}`;
            if (typeof event.id !== "string" || !event.id) {
                const parts = [ownerId, position, typeof event.command === "string" ? event.command : "event"];
                let id = stableResourceId(...parts);
                for (let salt = 1; taken.has(id); salt++)
                    id = stableResourceId(...parts, String(salt));
                taken.add(id);
                event.id = id;
            }
            if (!isObject(event.children))
                return;
            for (const [branch, children] of Object.entries(event.children)) {
                if (Array.isArray(children))
                    assign(children, `${position}/${branch}`, depth + 1);
            }
        });
    }
    for (const [key, events] of Object.entries(resource)) {
        if (SCRIPT_KEYS.test(key) && Array.isArray(events))
            assign(events, key, 0);
    }
    return resource;
}
export function withNativeScriptEventIds(resource) {
    return assignNativeScriptEventIds(structuredClone(resource));
}
function equivalentJson(left, right) {
    if (Object.is(left, right))
        return true;
    if (Array.isArray(left) || Array.isArray(right)) {
        return Array.isArray(left) && Array.isArray(right)
            && left.length === right.length
            && left.every((value, index) => equivalentJson(value, right[index]));
    }
    if (!isObject(left) || !isObject(right))
        return false;
    const leftKeys = Object.keys(left).sort();
    const rightKeys = Object.keys(right).sort();
    return leftKeys.length === rightKeys.length
        && leftKeys.every((key, index) => key === rightKeys[index]
            && equivalentJson(left[key], right[key]));
}
function withoutEventIds(event) {
    const stripped = { ...event };
    delete stripped.id;
    if (!isObject(event.children))
        return stripped;
    stripped.children = Object.fromEntries(Object.entries(event.children).map(([branch, children]) => [
        branch,
        Array.isArray(children) ? children.map((child) => isObject(child) ? withoutEventIds(child) : child) : children,
    ]));
    return stripped;
}
function validTypedArgument(key, value) {
    if (!isNativeScriptValue(value))
        return false;
    return key !== "direction" || value.type !== "direction" || SCRIPT_DIRECTIONS.has(value.value);
}
function typedArgumentMessage(event, eventId, key) {
    if (event.command === "EVENT_SWITCH_SCENE") {
        return `Event ${eventId} transition coordinate ${key} must be an official typed ScriptValue; use script_transition to create a valid scene transition`;
    }
    const value = isObject(event.args) ? event.args[key] : undefined;
    const example = key === "direction" ? '{"type":"direction","value":"up"}' : '{"type":"number","value":3}';
    if (value === undefined)
        return `Event ${eventId} (${event.command}) needs a ${key} argument such as ${example}`;
    if (isNativeScriptValue(value))
        return `Event ${eventId} (${event.command}) direction must be up, down, left or right, not ${JSON.stringify(value.value)}`;
    return `Event ${eventId} (${event.command}) argument ${key} must be a typed ScriptValue such as ${example}, not ${JSON.stringify(value)}`;
}
/**
 * Find newly introduced invalid native transitions without making an unrelated
 * edit responsible for malformed events that were already present historically.
 * Prefab argument overrides are intentionally excluded: their referenced event
 * commands live in separately resolved prefab resources, so treating every
 * override named x/y as a scene transition would reject valid native commands.
 */
export function findInvalidNativeScriptEvent(proposed, previous, options = {}) {
    const previousIndex = indexScriptEvents(previous);
    const existingEvents = previousIndex.events;
    const historicalWithoutId = previousIndex.orderedEvents
        .filter((event) => typeof event.id !== "string" || !event.id)
        .map(withoutEventIds);
    const historicalMatch = (event) => {
        const stripped = withoutEventIds(event);
        return historicalWithoutId.find((historical) => equivalentJson(historical, stripped));
    };
    const proposedEvents = indexScriptEvents(proposed, true);
    if (proposedEvents.error)
        return proposedEvents.error;
    for (const event of proposedEvents.orderedEvents) {
        const args = isObject(event.args) ? event.args : {};
        if (args.__comment)
            continue;
        const eventId = typeof event.id === "string" && event.id ? event.id : "unknown";
        const prior = (eventId === "unknown" ? undefined : existingEvents.get(eventId)) ?? historicalMatch(event);
        const priorArguments = isObject(prior?.args) ? prior.args : {};
        const revalidate = !prior || prior.command !== event.command || Boolean(priorArguments.__comment);
        const edited = options.explicitlyPatchedValues?.has(eventId) === true || !equivalentJson(priorArguments, args);
        const unbuildable = revalidate || edited ? unbuildableEventMessage(event.command, `Event ${eventId}`, options) : undefined;
        if (unbuildable)
            return { eventId, message: unbuildable };
        const keys = TYPED_EVENT_ARGUMENTS.get(event.command);
        if (!keys)
            continue;
        for (const key of keys) {
            const present = Object.prototype.hasOwnProperty.call(args, key);
            if (!present && !REQUIRED_EVENT_ARGUMENTS.has(key))
                continue;
            const explicitlyPatched = options.explicitlyPatchedValues?.get(eventId)?.has(key) === true;
            const changed = present !== Object.prototype.hasOwnProperty.call(priorArguments, key)
                || !equivalentJson(priorArguments[key], args[key]);
            if (!(revalidate || changed || explicitlyPatched))
                continue;
            if (present && validTypedArgument(key, args[key]))
                continue;
            return { eventId, argument: key, message: typedArgumentMessage(event, eventId, key) };
        }
    }
    return undefined;
}
