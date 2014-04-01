#pylint: disable=E1103, E1101

import copy
import logging
import re

from django.conf import settings
from django.utils.translation import ugettext as _

from xmodule.contentstore.content import StaticContent
from xmodule.contentstore.django import contentstore
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError
from xmodule.modulestore.locations import SlashSeparatedCourseKey
from django_comment_common.utils import unseed_permissions_roles
from xmodule.modulestore.store_utilities import delete_course
from xmodule.course_module import CourseDescriptor
from xmodule.modulestore.draft import DIRECT_ONLY_CATEGORIES
from student.roles import CourseInstructorRole, CourseStaffRole


log = logging.getLogger(__name__)

# In order to instantiate an open ended tab automatically, need to have this data
OPEN_ENDED_PANEL = {"name": _("Open Ended Panel"), "type": "open_ended"}
NOTES_PANEL = {"name": _("My Notes"), "type": "notes"}
EXTRA_TAB_PANELS = dict([(p['type'], p) for p in [OPEN_ENDED_PANEL, NOTES_PANEL]])


def delete_course_and_groups(course_id, commit=False):
    """
    This deletes the courseware associated with a course_id as well as cleaning update_item
    the various user table stuff (groups, permissions, etc.)
    """
    module_store = modulestore('direct')
    content_store = contentstore()

    module_store.ignore_write_events_on_courses.append(course_id)

    if delete_course(module_store, content_store, course_id, commit):

        print 'removing User permissions from course....'
        # in the django layer, we need to remove all the user permissions groups associated with this course
        if commit:
            try:
                staff_role = CourseStaffRole(course_id)
                staff_role.remove_users(*staff_role.users_with_role())
                instructor_role = CourseInstructorRole(course_id)
                instructor_role.remove_users(*instructor_role.users_with_role())
            except Exception as err:
                log.error("Error in deleting course groups for {0}: {1}".format(course_id, err))


def get_modulestore(category_or_location):
    """
    Returns the correct modulestore to use for modifying the specified location
    """
    if isinstance(category_or_location, Location):
        category_or_location = category_or_location.category

    if category_or_location in DIRECT_ONLY_CATEGORIES:
        return modulestore('direct')
    else:
        return modulestore()


def get_course_location_for_item(location):
    '''
    cdodge: for a given Xmodule, return the course that it belongs to
    NOTE: This makes a lot of assumptions about the format of the course location
    Also we have to assert that this module maps to only one course item - it'll throw an
    assert if not
    '''
    # check to see if item is already a course, if so we can skip this
    if location.category != 'course':
        # @hack! We need to find the course location however, we don't
        # know the 'name' parameter in this context, so we have
        # to assume there's only one item in this query even though we are not specifying a name
        courses = modulestore().get_items(location.course.id, qualifiers={'category': 'course'})

        # make sure we found exactly one match on this above course search
        found_cnt = len(courses)
        if found_cnt == 0:
            raise Exception('Could not find course for {0}'.format(location.course.id))

        if found_cnt > 1:
            raise Exception('Found more than one course for {0}. There should only be one!!! Dump = {1}'.format(location.course.id, courses))

        location = courses[0].location

    return location


def get_course_for_item(location):
    '''
    cdodge: for a given Xmodule, return the course that it belongs to
    NOTE: This makes a lot of assumptions about the format of the course location
    Also we have to assert that this module maps to only one course item - it'll throw an
    assert if not
    '''
    # @hack! We need to find the course location however, we don't
    # know the 'name' parameter in this context, so we have
    # to assume there's only one item in this query even though we are not specifying a name
    courses = modulestore().get_items(location.course.id, qualifiers={'category': 'course'})

    # make sure we found exactly one match on this above course search
    found_cnt = len(courses)
    if found_cnt == 0:
        raise BaseException('Could not find course for {0}'.format(location.course.id))

    if found_cnt > 1:
        raise BaseException('Found more than one course for {0}. There should only be one!!! Dump = {1}'.format(location.course.id, courses))

    return courses[0]


def get_lms_link_for_item(location, course_id, preview=False):
    """
    Returns an LMS link to the course with a jump_to to the provided location.

    :param location: the location to jump to
    :param course_id: the course_id within which the location lives.
    :param preview: True if the preview version of LMS should be returned. Default value is false.
    """
    if settings.LMS_BASE is not None:
        if preview:
            lms_base = settings.FEATURES.get('PREVIEW_LMS_BASE')
        else:
            lms_base = settings.LMS_BASE

        lms_link = u"//{lms_base}/courses/{course_id}/jump_to/{location}".format(
            lms_base=lms_base,
            course_id=course_id,
            location=location
        )
    else:
        lms_link = None

    return lms_link


def get_lms_link_for_about_page(course_id):
    """
    Returns the url to the course about page from the location tuple.
    """

    assert(isinstance(course_id, SlashSeparatedCourseKey))

    if settings.FEATURES.get('ENABLE_MKTG_SITE', False):
        if not hasattr(settings, 'MKTG_URLS'):
            log.exception("ENABLE_MKTG_SITE is True, but MKTG_URLS is not defined.")
            return None

        marketing_urls = settings.MKTG_URLS

        # Root will be "https://www.edx.org". The complete URL will still not be exactly correct,
        # but redirects exist from www.edx.org to get to the Drupal course about page URL.
        about_base = marketing_urls.get('ROOT')

        if about_base is None:
            log.exception('There is no ROOT defined in MKTG_URLS')
            return None

        # Strip off https:// (or http://) to be consistent with the formatting of LMS_BASE.
        about_base = re.sub(r"^https?://", "", about_base)

    elif settings.LMS_BASE is not None:
        about_base = settings.LMS_BASE
    else:
        return None

    return u"//{about_base_url}/courses/{course_id}/about".format(
        about_base_url=about_base,
        course_id=course_id.to_deprecated_string()
    )


def course_image_url(course):
    """Returns the image url for the course."""
    loc = StaticContent.compute_location(course.location.org, course.location.course, course.course_image)
    path = StaticContent.get_url_path_from_location(loc)
    return path


class PublishState(object):
    """
    The publish state for a given xblock-- either 'draft', 'private', or 'public'.

    Currently in CMS, an xblock can only be in 'draft' or 'private' if it is at or below the Unit level.
    """
    draft = 'draft'
    private = 'private'
    public = 'public'


def compute_publish_state(xblock):
    """
    Returns whether this xblock is 'draft', 'public', or 'private'.

    'draft' content is in the process of being edited, but still has a previous
        version visible in the LMS
    'public' content is locked and visible in the LMS
    'private' content is editable and not visible in the LMS
    """

    if getattr(xblock, 'is_draft', False):
        try:
            modulestore('direct').get_item(xblock.location)
            return PublishState.draft
        except ItemNotFoundError:
            return PublishState.private
    else:
        return PublishState.public


def add_extra_panel_tab(tab_type, course):
    """
    Used to add the panel tab to a course if it does not exist.
    @param tab_type: A string representing the tab type.
    @param course: A course object from the modulestore.
    @return: Boolean indicating whether or not a tab was added and a list of tabs for the course.
    """
    # Copy course tabs
    course_tabs = copy.copy(course.tabs)
    changed = False
    # Check to see if open ended panel is defined in the course

    tab_panel = EXTRA_TAB_PANELS.get(tab_type)
    if tab_panel not in course_tabs:
        # Add panel to the tabs if it is not defined
        course_tabs.append(tab_panel)
        changed = True
    return changed, course_tabs


def remove_extra_panel_tab(tab_type, course):
    """
    Used to remove the panel tab from a course if it exists.
    @param tab_type: A string representing the tab type.
    @param course: A course object from the modulestore.
    @return: Boolean indicating whether or not a tab was added and a list of tabs for the course.
    """
    # Copy course tabs
    course_tabs = copy.copy(course.tabs)
    changed = False
    # Check to see if open ended panel is defined in the course

    tab_panel = EXTRA_TAB_PANELS.get(tab_type)
    if tab_panel in course_tabs:
        # Add panel to the tabs if it is not defined
        course_tabs = [ct for ct in course_tabs if ct != tab_panel]
        changed = True
    return changed, course_tabs
