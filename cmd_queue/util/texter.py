# flake8: noqa
"""
An automatic lazy textual API

Example:
    from cmd_queue.util import texter
"""

__mkinit__ = """
mkinit textual --noattrs --lazy > ~/code/cmd_queue/cmd_queue/util/texter.py
"""


def lazy_import(module_name, submodules, submod_attrs):
    import importlib
    import os
    name_to_submod = {
        func: mod for mod, funcs in submod_attrs.items()
        for func in funcs
    }

    def __getattr__(name):
        if name in submodules:
            attr = importlib.import_module(
                '{module_name}.{name}'.format(
                    module_name=module_name, name=name)
            )
        elif name in name_to_submod:
            submodname = name_to_submod[name]
            module = importlib.import_module(
                '{module_name}.{submodname}'.format(
                    module_name=module_name, submodname=submodname)
            )
            attr = getattr(module, name)
        else:
            raise AttributeError(
                'No {module_name} attribute {name}'.format(
                    module_name=module_name, name=name))
        globals()[name] = attr
        return attr

    if os.environ.get('EAGER_IMPORT', ''):
        for name in submodules:
            __getattr__(name)

        for attrs in submod_attrs.values():
            for attr in attrs:
                __getattr__(attr)
    return __getattr__


__getattr__ = lazy_import(
    'textual',
    submodules={
        'actions',
        'app',
        'background',
        'binding',
        'case',
        'driver',
        'drivers',
        'events',
        'geometry',
        'keys',
        'layout',
        'layout_map',
        'layouts',
        'message',
        'message_pump',
        'messages',
        'page',
        'reactive',
        'screen_update',
        'scrollbar',
        'view',
        'views',
        'widget',
        'widgets',
    },
    submod_attrs={},
)


def __dir__():
    return __all__

__all__ = [
    'actions', 'app', 'background', 'binding', 'case', 'driver',
    'drivers', 'events', 'geometry', 'keys', 'layout', 'layout_map',
    'layouts', 'message', 'message_pump', 'messages', 'page',
    'reactive', 'screen_update', 'scrollbar', 'view', 'views', 'widget',
    'widgets']
