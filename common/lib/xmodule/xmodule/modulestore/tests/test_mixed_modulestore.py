import pymongo
from uuid import uuid4
import ddt
from mock import patch, Mock
from importlib import import_module

from xmodule.tests import DATA_DIR
from xmodule.modulestore import Location, MONGO_MODULESTORE_TYPE, SPLIT_MONGO_MODULESTORE_TYPE, \
    XML_MODULESTORE_TYPE
from xmodule.modulestore.exceptions import ItemNotFoundError

from xmodule.modulestore.locator import BlockUsageLocator, CourseLocator
from xmodule.modulestore.tests.test_location_mapper import LocMapperSetupSansDjango, loc_mapper
# Mixed modulestore depends on django, so we'll manually configure some django settings
# before importing the module
from django.conf import settings
if not settings.configured:
    settings.configure()
from xmodule.modulestore.mixed import MixedModuleStore


@ddt.ddt
class TestMixedModuleStore(LocMapperSetupSansDjango):
    """
    Quasi-superclass which tests Location based apps against both split and mongo dbs (Locator and
    Location-based dbs)
    """
    HOST = 'localhost'
    PORT = 27017
    DB = 'test_mongo_%s' % uuid4().hex[:5]
    COLLECTION = 'modulestore'
    FS_ROOT = DATA_DIR
    DEFAULT_CLASS = 'xmodule.raw_module.RawDescriptor'
    RENDER_TEMPLATE = lambda t_n, d, ctx = None, nsp = 'main': ''

    MONGO_COURSEID = 'MITx/999/2013_Spring'
    XML_COURSEID1 = 'edX/toy/2012_Fall'
    XML_COURSEID2 = 'edX/simple/2012_Fall'

    modulestore_options = {
        'default_class': DEFAULT_CLASS,
        'fs_root': DATA_DIR,
        'render_template': RENDER_TEMPLATE,
    }
    DOC_STORE_CONFIG = {
        'host': HOST,
        'db': DB,
        'collection': COLLECTION,
    }
    OPTIONS = {
        'mappings': {
            XML_COURSEID1: 'xml',
            XML_COURSEID2: 'xml',
            MONGO_COURSEID: 'default'
        },
        'stores': {
            'xml': {
                'ENGINE': 'xmodule.modulestore.xml.XMLModuleStore',
                'OPTIONS': {
                    'data_dir': DATA_DIR,
                    'default_class': 'xmodule.hidden_module.HiddenDescriptor',
                }
            },
            'direct': {
                'ENGINE': 'xmodule.modulestore.mongo.MongoModuleStore',
                'DOC_STORE_CONFIG': DOC_STORE_CONFIG,
                'OPTIONS': modulestore_options
            },
            'draft': {
                'ENGINE': 'xmodule.modulestore.mongo.MongoModuleStore',
                'DOC_STORE_CONFIG': DOC_STORE_CONFIG,
                'OPTIONS': modulestore_options
            },
            'split': {
                'ENGINE': 'xmodule.modulestore.split_mongo.SplitMongoModuleStore',
                'DOC_STORE_CONFIG': DOC_STORE_CONFIG,
                'OPTIONS': modulestore_options
            }
        }
    }

    def _compareIgnoreVersion(self, loc1, loc2, msg=None):
        """
        AssertEqual replacement for CourseLocator
        """
        if not (loc1.package_id == loc2.package_id and loc1.branch == loc2.branch and loc1.block_id == loc2.block_id):
            self.fail(self._formatMessage(msg, u"{} != {}".format(unicode(loc1), unicode(loc2))))

    def setUp(self):
        """
        Set up the database for testing
        """
        self.options = getattr(self, 'options', self.OPTIONS)
        self.connection = pymongo.MongoClient(
            host=self.HOST,
            port=self.PORT,
            tz_aware=True,
        )
        self.connection.drop_database(self.DB)
        self.addCleanup(self.connection.drop_database, self.DB)
        self.addCleanup(self.connection.close)
        super(TestMixedModuleStore, self).setUp()

        patcher = patch.multiple(
            'xmodule.modulestore.mixed',
            loc_mapper=Mock(return_value=LocMapperSetupSansDjango.loc_store),
            create_modulestore_instance=create_modulestore_instance,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addTypeEqualityFunc(BlockUsageLocator, '_compareIgnoreVersion')
        # define attrs which get set in initdb to quell pylint
        self.import_chapter_location = self.store = self.fake_location = self.xml_chapter_location = None
        self.course_locations = []

    # pylint: disable=invalid-name
    def _create_course(self, default, course_id):
        """
        Create a course w/ one item in the persistence store using the given course & item location.
        """
        course = self.store.create_course(course_id, store_name=default)
        category = self.import_chapter_location.category
        block_id = self.import_chapter_location.name
        chapter = self.store.create_item(
            # don't use course_location as it may not be the repr
            course.location, category, location=self.import_chapter_location, block_id=block_id
        )
        if isinstance(course.location, CourseLocator):
            self.course_locations[self.MONGO_COURSEID] = course.location.version_agnostic()
            self.import_chapter_location = chapter.location.version_agnostic()
        else:
            self.assertEqual(course.id, course_id)
            self.assertEqual(chapter.location, self.import_chapter_location)

    def initdb(self, default):
        """
        Initialize the database and create one test course in it
        """
        # set the default modulestore
        self.options['stores']['default'] = self.options['stores'][default]
        self.store = MixedModuleStore(**self.options)
        self.addCleanup(self.store.close_all_connections)

        self.course_locations = {
            course_id: course_id
            for course_id in [self.MONGO_COURSEID, self.XML_COURSEID1, self.XML_COURSEID2]
        }
        self.fake_location = Location('i4x', 'foo', 'bar', 'vertical', 'baz')
        self.import_chapter_location = self.course_locations[self.MONGO_COURSEID].replace(
            category='chapter', name='Overview'
        )
        self.xml_chapter_location = self.course_locations[self.XML_COURSEID1].replace(
            category='chapter', name='Overview'
        )
        # get Locators and set up the loc mapper if app is Locator based
        if default == 'split':
            self.fake_location = loc_mapper().translate_location(self.fake_location)

        self._create_course(default, self.MONGO_COURSEID)

    @ddt.data('direct', 'split')
    def test_get_modulestore_type(self, default_ms):
        """
        Make sure we get back the store type we expect for given mappings
        """
        self.initdb(default_ms)
        self.assertEqual(self.store.get_modulestore_type(self.XML_COURSEID1), XML_MODULESTORE_TYPE)
        self.assertEqual(self.store.get_modulestore_type(self.XML_COURSEID2), XML_MODULESTORE_TYPE)
        mongo_ms_type = MONGO_MODULESTORE_TYPE if default_ms == 'direct' else SPLIT_MONGO_MODULESTORE_TYPE
        self.assertEqual(self.store.get_modulestore_type(self.MONGO_COURSEID), mongo_ms_type)
        # try an unknown mapping, it should be the 'default' store
        self.assertEqual(self.store.get_modulestore_type('foo/bar/2012_Fall'), mongo_ms_type)

    @ddt.data('direct', 'split')
    def test_has_item(self, default_ms):
        self.initdb(default_ms)
        for course_id, course_locn in self.course_locations.iteritems():
            self.assertTrue(self.store.has_item(course_id, course_locn))

        # try negative cases
        self.assertFalse(self.store.has_item(
            self.XML_COURSEID1,
            self.course_locations[self.XML_COURSEID1].replace(name='not_findable', category='problem')
        ))
        self.assertFalse(self.store.has_item(self.MONGO_COURSEID, self.fake_location))

    @ddt.data('direct', 'split')
    def test_get_item(self, default_ms):
        self.initdb(default_ms)
        for course_id, course_locn in self.course_locations.iteritems():
            self.assertIsNotNone(self.store.get_item(course_locn))

        # try negative cases
        with self.assertRaises(ItemNotFoundError):
            self.store.get_item(
                self.course_locations[self.XML_COURSEID1].replace(name='not_findable', category='problem')
            )
        with self.assertRaises(ItemNotFoundError):
            self.store.get_item(self.fake_location)

    @ddt.data('direct', 'split')
    def test_get_items(self, default_ms):
        self.initdb(default_ms)
        for course_id, course_locn in self.course_locations.iteritems():
            if hasattr(course_locn, 'as_course_locator'):
                locn = course_locn.as_course_locator()
            else:
                locn = course_locn.replace(org=None, course=None, name=None)
            # NOTE: use get_course if you just want the course. get_items is expensive
            modules = self.store.get_items(locn, course_id, qualifiers={'category': 'course'})
            self.assertEqual(len(modules), 1)
            self.assertEqual(modules[0].location, course_locn)

    @ddt.data('direct', 'split')
    def test_update_item(self, default_ms):
        """
        Update should fail for r/o dbs and succeed for r/w ones
        """
        self.initdb(default_ms)
        course = self.store.get_course(self.XML_COURSEID1)
        # if following raised, then the test is really a noop, change it
        self.assertFalse(course.show_calculator, "Default changed making test meaningless")
        course.show_calculator = True
        with self.assertRaises(NotImplementedError):
            self.store.update_item(course, None)
        # now do it for a r/w db
        course = self.store.get_course(self.MONGO_COURSEID)
        # if following raised, then the test is really a noop, change it
        self.assertFalse(course.show_calculator, "Default changed making test meaningless")
        course.show_calculator = True
        self.store.update_item(course, None)
        course = self.store.get_course(self.MONGO_COURSEID)
        self.assertTrue(course.show_calculator)

    @ddt.data('direct', 'split')
    def test_delete_item(self, default_ms):
        """
        Delete should reject on r/o db and work on r/w one
        """
        self.initdb(default_ms)
        # r/o try deleting the course
        with self.assertRaises(NotImplementedError):
            self.store.delete_item(self.xml_chapter_location)
        self.store.delete_item(self.import_chapter_location, '**replace_user**')
        # verify it's gone
        with self.assertRaises(ItemNotFoundError):
            self.store.get_item(self.import_chapter_location)

    @ddt.data('direct', 'split')
    def test_get_courses(self, default_ms):
        self.initdb(default_ms)
        # we should have 3 total courses across all stores
        courses = self.store.get_courses()
        course_ids = [
            course.location.version_agnostic()
            if hasattr(course.location, 'version_agnostic') else course.location
            for course in courses
        ]
        self.assertEqual(len(courses), 3, "Not 3 courses: {}".format(course_ids))
        self.assertIn(self.course_locations[self.MONGO_COURSEID], course_ids)
        self.assertIn(self.course_locations[self.XML_COURSEID1], course_ids)
        self.assertIn(self.course_locations[self.XML_COURSEID2], course_ids)

    def test_xml_get_courses(self):
        """
        Test that the xml modulestore only loaded the courses from the maps.
        """
        self.initdb('direct')
        courses = self.store.modulestores['xml'].get_courses()
        self.assertEqual(len(courses), 2)
        course_ids = [course.id for course in courses]
        self.assertIn(self.XML_COURSEID1, course_ids)
        self.assertIn(self.XML_COURSEID2, course_ids)
        # this course is in the directory from which we loaded courses but not in the map
        self.assertNotIn("edX/toy/TT_2012_Fall", course_ids)

    def test_xml_no_write(self):
        """
        Test that the xml modulestore doesn't allow write ops.
        """
        self.initdb('direct')
        with self.assertRaises(NotImplementedError):
            self.store.create_course("org/course/run", store_name='xml')

    @ddt.data('direct', 'split')
    def test_get_course(self, default_ms):
        self.initdb(default_ms)
        for course_id in self.course_ids:
            # NOTE: use get_course if you just want the course. get_items is expensive
            course = self.store.get_course(course_id)
            self.assertIsNotNone(course)
            self.assertEqual(course.id, course_id)

    @ddt.data('direct', 'split')
    def test_get_parent_locations(self, default_ms):
        self.initdb(default_ms)
        parents = self.store.get_parent_locations(
            self.import_chapter_location,
            self.MONGO_COURSEID
        )
        self.assertEqual(len(parents), 1)
        self.assertEqual(parents[0], self.course_locations[self.MONGO_COURSEID])

        parents = self.store.get_parent_locations(
            self.xml_chapter_location,
            self.XML_COURSEID1
        )
        self.assertEqual(len(parents), 1)
        self.assertEqual(parents[0], self.course_locations[self.XML_COURSEID1])

    @ddt.data('direct', 'split')
    def test_get_orphans(self, default_ms):
        self.initdb(default_ms)
        # create an orphan
        if default_ms == 'split':
            course_id = self.course_locations[self.MONGO_COURSEID].as_course_locator()
            branch = course_id.branch
        else:
            course_id = self.MONGO_COURSEID
            branch = None
        orphan = self.store.create_item(course_id, 'problem', block_id='orphan')
        found_orphans = self.store.get_orphans(self.course_locations[self.MONGO_COURSEID], branch)
        if default_ms == 'split':
            self.assertEqual(found_orphans, [orphan.location.version_agnostic()])
        else:
            self.assertEqual(found_orphans, [unicode(orphan.location)])

    @ddt.data('split')
    def test_create_item_from_course_id(self, default_ms):
        """
        Test code paths missed by the above:
        * passing an old-style course_id which has a loc map to split's create_item
        """
        self.initdb(default_ms)
        # create loc_map entry
        loc_mapper().translate_location(self.MONGO_COURSEID)
        orphan = self.store.create_item(self.MONGO_COURSEID, 'problem', block_id='orphan')
        self.assertEqual(
            orphan.location.version_agnostic().as_course_locator(),
            self.course_locations[self.MONGO_COURSEID].as_course_locator()
        )

    @ddt.data('direct')
    def test_create_item_from_parent_location(self, default_ms):
        """
        Test a code path missed by the above: passing an old-style location as parent but no
        new location for the child
        """
        self.initdb(default_ms)
        self.store.create_item(self.course_locations[self.MONGO_COURSEID], 'problem', block_id='orphan')
        orphans = self.store.get_orphans(self.course_locations[self.MONGO_COURSEID], None)
        self.assertEqual(len(orphans), 0, "unexpected orphans: {}".format(orphans))

    @ddt.data('direct')
    def test_get_courses_for_wiki(self, default_ms):
        """
        Test the get_courses_for_wiki method
        """
        self.initdb(default_ms)
        course_locations = self.store.get_courses_for_wiki('toy')
        self.assertEqual(len(course_locations), 1)
        self.assertIn(Location('i4x', 'edX', 'toy', 'course', '2012_Fall'), course_locations)

        course_locations = self.store.get_courses_for_wiki('simple')
        self.assertEqual(len(course_locations), 1)
        self.assertIn(Location('i4x', 'edX', 'simple', 'course', '2012_Fall'), course_locations)

        self.assertEqual(len(self.store.get_courses_for_wiki('edX.simple.2012_Fall')), 0)
        self.assertEqual(len(self.store.get_courses_for_wiki('no_such_wiki')), 0)


#=============================================================================================================
# General utils for not using django settings
#=============================================================================================================


def load_function(path):
    """
    Load a function by name.

    path is a string of the form "path.to.module.function"
    returns the imported python object `function` from `path.to.module`
    """
    module_path, _, name = path.rpartition('.')
    return getattr(import_module(module_path), name)


# pylint: disable=unused-argument
def create_modulestore_instance(engine, doc_store_config, options, i18n_service=None):
    """
    This will return a new instance of a modulestore given an engine and options
    """
    class_ = load_function(engine)

    return class_(
        doc_store_config=doc_store_config,
        **options
    )
