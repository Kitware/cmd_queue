# flake8: noqa
"""
An automatic lazy rich API

Example:
    from cmd_queue.util import richer as rich
"""

__mkinit__ = """
mkinit rich --noattrs --lazy > ~/code/cmd_queue/cmd_queue/util/richer.py
"""


# Global console used by alternative print
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
    'rich',
    submodules={
        'abc',
        'align',
        'ansi',
        'bar',
        'box',
        'cells',
        'color',
        'color_triplet',
        'columns',
        'console',
        'constrain',
        'containers',
        'control',
        'default_styles',
        'diagnose',
        'emoji',
        'errors',
        'file_proxy',
        'filesize',
        'highlighter',
        'json',
        'jupyter',
        'layout',
        'live',
        'live_render',
        'logging',
        'markdown',
        'markup',
        'measure',
        'padding',
        'pager',
        'palette',
        'panel',
        'pretty',
        'progress',
        'progress_bar',
        'prompt',
        'protocol',
        'region',
        'repr',
        'rule',
        'scope',
        'screen',
        'segment',
        'spinner',
        'status',
        'style',
        'styled',
        'syntax',
        'table',
        'terminal_theme',
        'text',
        'theme',
        'themes',
        'traceback',
        'tree',
    },
    submod_attrs={},
)


def __dir__():
    return __all__

__all__ = ['abc', 'align', 'ansi', 'bar', 'box', 'cells', 'color',
           'color_triplet', 'columns', 'console', 'constrain', 'containers',
           'control', 'default_styles', 'diagnose', 'emoji', 'errors',
           'file_proxy', 'filesize', 'get_console', 'highlighter', 'inspect',
           'json', 'jupyter', 'layout', 'live', 'live_render', 'logging',
           'markdown', 'markup', 'measure', 'padding', 'pager', 'palette',
           'panel', 'pretty', 'print', 'progress', 'progress_bar', 'prompt',
           'protocol', 'reconfigure', 'region', 'repr', 'rule', 'scope',
           'screen', 'segment', 'spinner', 'status', 'style', 'styled',
           'syntax', 'table', 'terminal_theme', 'text', 'theme', 'themes',
           'traceback', 'tree']
