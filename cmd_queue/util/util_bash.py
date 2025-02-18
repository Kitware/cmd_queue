def bash_json_dump(json_fmt_parts, fpath):
    r"""
    Generate a printf bash command that dumps a JSON file indicating some
    status in a bash environment.

    Args:
        List[Tuple[str, str, str]]: A list of 3-tuples where each tuple contains:
            - The JSON key (str)
            - The printf format string (str)
            - The bash expression (str) that provides the value to be printed

        fpath (str): Path where the bash script should write the JSON file.

    Returns:
        str: The bash command that will perform the printf.

    Example:
        >>> from cmd_queue.util.util_bash import *  # NOQA
        >>> json_fmt_parts = [
        >>>     ('home', '%s', '$HOME'),
        >>>     ('const', '%s', 'MY_CONSTANT'),
        >>>     ('ps2', '"%s"', '$PS2'),
        >>> ]
        >>> fpath = 'out.json'
        >>> dump_code = bash_json_dump(json_fmt_parts, fpath)
        >>> print(dump_code)
        printf '{"home": %s, "const": %s, "ps2": "%s"}\n' \
            "$HOME" "MY_CONSTANT" "$PS2" \
            > out.json

    Example:
        >>> from cmd_queue.util.util_bash import *  # NOQA
        >>> json_fmt_parts = []
        >>> fpath = 'out.json'
        >>> dump_code = bash_json_dump(json_fmt_parts, fpath)
        >>> print(dump_code)
        printf '{}\n' \
             \
            > out.json
    """
    printf_body_parts = [
        '"{}": {}'.format(k, f) for k, f, v in json_fmt_parts
    ]
    printf_arg_parts = [
        '"{}"'.format(v) for k, f, v in json_fmt_parts
    ]
    printf_body = r"'{" + ", ".join(printf_body_parts) + r"}\n'"
    printf_args = ' '.join(printf_arg_parts)
    redirect_part = '> ' + str(fpath)
    printf_part = 'printf ' +  printf_body + ' \\\n    ' + printf_args
    dump_code = printf_part + ' \\\n    ' + redirect_part
    return dump_code
