import courseware.access as access
import datetime

from mock import Mock

from django.test import TestCase
from django.test.utils import override_settings

from courseware.tests.factories import UserFactory, CourseEnrollmentAllowedFactory, StaffFactory, InstructorFactory
from student.tests.factories import AnonymousUserFactory
from xmodule.modulestore import Location
from courseware.tests.tests import TEST_DATA_MIXED_MODULESTORE
import pytz


# pylint: disable=protected-access
@override_settings(MODULESTORE=TEST_DATA_MIXED_MODULESTORE)
class AccessTestCase(TestCase):
    """
    Tests for the various access controls on the student dashboard
    """

    def setUp(self):
        self.course = Location('i4x://edX/toy/course/2012_Fall')
        self.anonymous_user = AnonymousUserFactory()
        self.student = UserFactory()
        self.global_staff = UserFactory(is_staff=True)
        self.course_staff = StaffFactory(course=self.course.course_id)
        self.course_instructor = InstructorFactory(course=self.course.course_id)

    def test__has_access_to_location(self):
        self.assertFalse(access._has_access_to_location(
            None, 'staff', self.course, self.course.course_id
        ))

        self.assertFalse(access._has_access_to_location(
            self.anonymous_user, 'staff', self.course, self.course.course_id
        ))
        self.assertFalse(access._has_access_to_location(
            self.anonymous_user, 'instructor', self.course, self.course.course_id
        ))

        self.assertTrue(access._has_access_to_location(
            self.global_staff, 'staff', self.course, self.course.course_id
        ))
        self.assertTrue(access._has_access_to_location(
            self.global_staff, 'instructor', self.course, self.course.course_id
        ))

        # A user has staff access if they are in the staff group
        self.assertTrue(access._has_access_to_location(
            self.course_staff, 'staff', self.course, self.course.course_id
        ))
        self.assertFalse(access._has_access_to_location(
            self.course_staff, 'instructor', self.course, self.course.course_id
        ))

        # A user has staff and instructor access if they are in the instructor group
        self.assertTrue(access._has_access_to_location(
            self.course_instructor, 'staff', self.course, self.course.course_id
        ))
        self.assertTrue(access._has_access_to_location(
            self.course_instructor, 'instructor', self.course, self.course.course_id
        ))

        # A user does not have staff or instructor access if they are
        # not in either the staff or the the instructor group
        self.assertFalse(access._has_access_to_location(
            self.student, 'staff', self.course, self.course.course_id
        ))
        self.assertFalse(access._has_access_to_location(
            self.student, 'instructor', self.course, self.course.course_id
        ))

    def test__has_access_string(self):
        u = Mock(is_staff=True)
        self.assertFalse(access._has_access_string(u, 'staff', 'not_global', self.course.course_id))

        u._has_global_staff_access.return_value = True
        self.assertTrue(access._has_access_string(u, 'staff', 'global', self.course.course_id))

        self.assertRaises(ValueError, access._has_access_string, u, 'not_staff', 'global', self.course.course_id)

    def test__has_access_descriptor(self):
        # TODO: override DISABLE_START_DATES and test the start date branch of the method
        u = Mock()
        d = Mock()
        d.start = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=1)  # make sure the start time is in the past

        # Always returns true because DISABLE_START_DATES is set in test.py
        self.assertTrue(access._has_access_descriptor(u, 'load', d))
        with self.assertRaises(ValueError):
            access._has_access_descriptor(u, 'not_load_or_staff', d)

    def test__has_access_course_desc_can_enroll(self):
        u = Mock()
        yesterday = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=1)
        tomorrow = datetime.datetime.now(pytz.utc) + datetime.timedelta(days=1)
        c = Mock(enrollment_start=yesterday, enrollment_end=tomorrow, enrollment_domain='')

        # User can enroll if it is between the start and end dates
        self.assertTrue(access._has_access_course_desc(u, 'enroll', c))

        # User can enroll if authenticated and specifically allowed for that course
        # even outside the open enrollment period
        u = Mock(email='test@edx.org', is_staff=False)
        u.is_authenticated.return_value = True

        c = Mock(enrollment_start=tomorrow, enrollment_end=tomorrow, id='edX/test/2012_Fall', enrollment_domain='')

        allowed = CourseEnrollmentAllowedFactory(email=u.email, course_id=c.id)

        self.assertTrue(access._has_access_course_desc(u, 'enroll', c))

        # Staff can always enroll even outside the open enrollment period
        u = Mock(email='test@edx.org', is_staff=True)
        u.is_authenticated.return_value = True

        c = Mock(enrollment_start=tomorrow, enrollment_end=tomorrow, id='edX/test/Whenever', enrollment_domain='')
        self.assertTrue(access._has_access_course_desc(u, 'enroll', c))

        # TODO:
        # Non-staff cannot enroll outside the open enrollment period if not specifically allowed

    def test__user_passed_as_none(self):
        """Ensure has_access handles a user being passed as null"""
        access.has_access(None, 'staff', 'global', None)


class UserRoleTestCase(TestCase):
    """
    Tests for user roles.
    """
    def setUp(self):
        self.course = Location('i4x://edX/toy/course/2012_Fall')
        self.anonymous_user = AnonymousUserFactory()
        self.student = UserFactory()
        self.global_staff = UserFactory(is_staff=True)
        self.course_staff = StaffFactory(course=self.course.course_id)
        self.course_instructor = InstructorFactory(course=self.course.course_id)

    def test_user_role_staff(self):
        """Ensure that user role is student for staff masqueraded as student."""
        self.assertEqual(
            'staff',
            access.get_user_role(self.course_staff, self.course.course_id)
        )
        # Masquerade staff
        self.course_staff.masquerade_as_student = True
        self.assertEqual(
            'student',
            access.get_user_role(self.course_staff, self.course.course_id)
        )

    def test_user_role_instructor(self):
        """Ensure that user role is student for instructor masqueraded as student."""
        self.assertEqual(
            'instructor',
            access.get_user_role(self.course_instructor, self.course.course_id)
        )
        # Masquerade instructor
        self.course_instructor.masquerade_as_student = True
        self.assertEqual(
            'student',
            access.get_user_role(self.course_instructor, self.course.course_id)
        )

    def test_user_role_anonymous(self):
        """Ensure that user role is student for anonymous user."""
        self.assertEqual(
            'student',
            access.get_user_role(self.anonymous_user, self.course.course_id)
        )
