"""
Unit tests for checking default forum role "Student" of a user when he creates a course or
after deleting it creates same course again
"""
from contentstore.tests.utils import AjaxEnabledTestClient
from contentstore.utils import delete_course_and_groups
from courseware.tests.factories import UserFactory
from xmodule.modulestore import Location
from xmodule.modulestore.django import loc_mapper
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from student.models import CourseEnrollment


class TestUsersDefaultRole(ModuleStoreTestCase):
    """
    Unit tests for checking enrollment and default forum role "Student" of a logged in user
    """
    def setUp(self):
        """
        Add a user and a course
        """
        super(TestUsersDefaultRole, self).setUp()
        # create and log in a staff user.
        self.user = UserFactory(is_staff=True)  # pylint: disable=no-member
        self.client = AjaxEnabledTestClient()
        self.client.login(username=self.user.username, password='test')

        # create a course via the view handler to create course
        self.course_location = Location(['i4x', 'Org_1', 'Course_1', 'course', 'Run_1'])
        self._create_course_with_given_location(self.course_location)

    def _create_course_with_given_location(self, course_location):
        """
        Create course at provided location
        """
        course_locator = loc_mapper().translate_location(course_location, False, True)
        resp = self.client.ajax_post(
            course_locator.url_reverse('course'),
            {
                'org': course_location.org,
                'number': course_location.course,
                'display_name': 'test course',
                'run': course_location.name,
            }
        )
        return resp

    def tearDown(self):
        """
        Reverse the setup
        """
        self.client.logout()
        super(TestUsersDefaultRole, self).tearDown()

    def test_user_forum_default_role_on_course_deletion(self):
        """
        Test that a user enrolls and gets "Student" forum role for that course which he creates and remains
        enrolled even the course is deleted and keeps its "Student" forum role for that course
        """
        course_id = self.course_location.course_key
        # check that user has enrollment for this course
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, course_id))

        # check that user has his default "Student" forum role for this course
        self.assertTrue(self.user.roles.filter(name="Student", course_id=course_id))  # pylint: disable=no-member

        delete_course_and_groups(course_id, commit=True)

        # check that user's enrollment for this course is not deleted
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, course_id))

        # check that user has forum role for this course even after deleting it
        self.assertTrue(self.user.roles.filter(name="Student", course_id=course_id))  # pylint: disable=no-member

    def test_user_role_on_course_recreate(self):
        """
        Test that creating same course again after deleting it gives user his default
        forum role "Student" for that course
        """
        course_id = self.course_location.course_key
        # check that user has enrollment and his default "Student" forum role for this course
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, course_id))
        self.assertTrue(self.user.roles.filter(name="Student", course_id=course_id))  # pylint: disable=no-member

        # delete this course and recreate this course with same user
        delete_course_and_groups(course_id, commit=True)
        resp = self._create_course_with_given_location(self.course_location)
        self.assertEqual(resp.status_code, 200)

        # check that user has his enrollment for this course
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, course_id))

        # check that user has his default "Student" forum role for this course
        self.assertTrue(self.user.roles.filter(name="Student", course_id=course_id))  # pylint: disable=no-member

    def test_user_role_on_course_recreate_with_change_name_case(self):
        """
        Test that creating same course again with different name case after deleting it gives user
        his default forum role "Student" for that course
        """
        course_location = self.course_location
        # check that user has enrollment and his default "Student" forum role for this course
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, course_location.course_key))
        # delete this course and recreate this course with same user
        delete_course_and_groups(course_location.course_key, commit=True)

        # now create same course with different name case ('uppercase')
        new_course_location = Location(
            ['i4x', course_location.org, course_location.course.upper(), 'course', course_location.name]
        )
        resp = self._create_course_with_given_location(new_course_location)
        self.assertEqual(resp.status_code, 200)

        # check that user has his default "Student" forum role again for this course (with changed name case)
        self.assertTrue(
            self.user.roles.filter(name="Student", course_id=new_course_location.course_key)  # pylint: disable=no-member
        )

        # Disabled due to case-sensitive test db (sqlite3)
        # # check that there user has only one "Student" forum role (with new updated course_id)
        # self.assertEqual(self.user.roles.filter(name='Student').count(), 1)  # pylint: disable=no-member
        # self.assertEqual(self.user.roles.filter(name='Student')[0].course_id, new_course_location.course_key)
