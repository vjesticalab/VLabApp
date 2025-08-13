# Plugins

To add a new *Hello World* plugin:

1. Create a new folder named `hello_world/` inside the `plugins/` folder, which is located in the VLabApp installation directory.

2. In the `hello_world/` folder, create a file named `__init__.py`. Your folder structure should look like:

        VLabApp/
        ├── plugins/
        │   └── hello_world/
        │       └── __init__.py
        │

    
3. Add the following python code to `__init__.py`:

        from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
        
        # Name of the plugin (used in the left panel of the GUI)
        NAME = 'Hello World!'
        
        # The widget (shown in the right panel of the GUI)
        class Widget(QWidget):
            def __init__(self, pipeline_layout=False):
                super().__init__()
                layout = QVBoxLayout()
                self.setLayout(layout)
                label = QLabel('Hello world!')
                layout.addWidget(label)

    Notes:
    
    * The `__init__.py` file must define a variable `NAME`, whose value will be displayed in the left panel of VLabApp as the plugin name.
    * It must also defined a class named `Widget`, that is a subclass of `QWidget`. It will appear in the right panel when clicking on the plugin name in the left panel.

4. Start VLabApp. The new "Hello World!" plugin should appear in the left panel inside the "Plugins" section.

