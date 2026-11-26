// The error every project operation throws, with a stable code and the resource it concerns. A module of its own,
// with no imports, so a small module such as project-files.js can throw it without loading the project model.
export class GameStudioProjectError extends Error {
    code;
    resourcePath;
    constructor(code, message, resourcePath) {
        super(message);
        this.code = code;
        this.resourcePath = resourcePath;
        this.name = "GameStudioProjectError";
    }
}
