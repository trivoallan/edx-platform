import re

# Prefix for the branch portion of a locator URL
BRANCH_PREFIX = r"branch/"
# Prefix for the block portion of a locator URL
BLOCK_PREFIX = r"block/"
# Prefix for the version portion of a locator URL, when it is preceded by a course ID
VERSION_PREFIX = r"version/"

ALLOWED_ID_CHARS = r'[\w\-~.:]'


URL_RE_SOURCE = r"""
    (?P<tag>edx://)?
    ((?P<org>{ALLOWED_ID_CHARS}+)\+(?P<offering>{ALLOWED_ID_CHARS}+)/?)?
    ({BRANCH_PREFIX}(?P<branch>{ALLOWED_ID_CHARS}+)/?)?
    ({VERSION_PREFIX}(?P<version_guid>[A-F0-9]+)/?)?
    ({BLOCK_PREFIX}(?P<block>{ALLOWED_ID_CHARS}+))?
    """.format(
        ALLOWED_ID_CHARS=ALLOWED_ID_CHARS, BRANCH_PREFIX=BRANCH_PREFIX,
        VERSION_PREFIX=VERSION_PREFIX, BLOCK_PREFIX=BLOCK_PREFIX
    )

URL_RE = re.compile('^' + URL_RE_SOURCE + '$', re.IGNORECASE | re.VERBOSE | re.UNICODE)


def parse_url(string, tag_optional=False):
    """
    A url usually begins with 'edx://' (case-insensitive match),
    followed by either a version_guid or a package_id. If tag_optional, then
    the url does not have to start with the tag and edx will be assumed.

    Examples:
        'edx://version/0123FFFF'
        'edx://mit.eecs.6002x'
        'edx://mit.eecs.6002x/branch/published'
        'edx://mit.eecs.6002x/branch/published/block/HW3'
        'edx://mit.eecs.6002x/branch/published/version/000eee12345/block/HW3'

    This returns None if string cannot be parsed.

    If it can be parsed as a version_guid with no preceding package_id, returns a dict
    with key 'version_guid' and the value,

    If it can be parsed as a package_id, returns a dict
    with key 'id' and optional keys 'branch' and 'version_guid'.

    """
    match = URL_RE.match(string)
    if not match:
        return None
    matched_dict = match.groupdict()
    if matched_dict['tag'] is None and not tag_optional:
        return None
    return matched_dict


BLOCK_RE = re.compile(r'^{}+$'.format(ALLOWED_ID_CHARS), re.IGNORECASE | re.UNICODE)


def parse_block_ref(string):
    r"""
    A block_ref is a string of url safe characters (see ALLOWED_ID_CHARS)

    If string is a block_ref, returns a dict with key 'block_ref' and the value,
    otherwise returns None.
    """
    if len(string) > 0 and BLOCK_RE.match(string):
        return {'block_id': string}
    return None
