"""Game images for the Build page: the asset RPCs, sprite and scene reading, and the kept versions of each
image (hooks keep what a reply showed or a tool looked at; a listener keeps what a build card shows).

Front door: nothing is exported; other features reach assets through events.
"""

__all__: list[str] = []

EVENTS = {
    "assets.image_restored": (
        "The asset viewer put a kept version of an image back; path=<the image's absolute path, str>"
    ),
}
