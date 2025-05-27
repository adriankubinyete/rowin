from tkinter import ttk


def root_disable_notebook_page_focus(root):
    style = ttk.Style(root)
    style.layout(
        "TNotebook.Tab",
        [
            (
                "Notebook.tab",
                {
                    "sticky": "nswe",
                    "children": [
                        (
                            "Notebook.padding",
                            {
                                "side": "top",
                                "sticky": "nswe",
                                "children": [
                                    # Removendo o foco
                                    ("Notebook.label", {"side": "top", "sticky": ""})
                                ],
                            },
                        )
                    ],
                },
            )
        ],
    )
