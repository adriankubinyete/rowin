import logging

from src.app.Application import Application
from src.app.utils.logging import console_handler

if __name__ == "__main__":
    logger = logging.getLogger("app")
    logger.setLevel(logging.TEST)
    logger.addHandler(console_handler)
    app = Application(
        title="Roblox Window Manager",
        width=400,
        height=450,
        resizeable=False,
        exceptionHandler=lambda *args: None,
        logger=logger,
    )
    app.root.mainloop()
