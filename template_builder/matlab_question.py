"""TO-DO: Write a description of what this XBlock is."""

import sys
import pkg_resources

from xblock.core import XBlock
from xblock.fields import Scope, JSONField, Integer, String, Boolean, Dict
from xblock.fragment import Fragment

from xblock.exceptions import JsonHandlerError, NoSuchViewError
from xblock.validation import Validation

from submissions import api as sub_api
from sub_api_util import SubmittingXBlockMixin

from xblockutils.studio_editable import StudioEditableXBlockMixin, FutureFields
from xblockutils.resources import ResourceLoader

import matlab_service
import matlab_question_service
import qgb_db_service
import json
from resolver_machine import resolver_machine

# import xblock_deletion_handler

import xml_helper

loader = ResourceLoader(__name__)

# Constants
ADVANCED_EDITOR_NAME = 'Advanced Editor'
SIMPLE_EDITOR_NAME = 'Simple Template'

def _(text):
    return text


@XBlock.needs("i18n")
class MatlabQuestionXBlock(XBlock, SubmittingXBlockMixin, StudioEditableXBlockMixin):
    """
    Question Generator XBlock
    """
    #
    CATEGORY = 'tb-matlab-question-generator'
    STUDIO_LABEL = _(u'Matlab Question')

    display_name = String(
        display_name="Display Name",
        help="This name appears in the horizontal navigation at the top of the page.",
        scope=Scope.settings,
        default="Matlab Question"
    )

    max_attempts = Integer(
        display_name="Maximum Attempts",
        help="Defines the number of times a student can try to answer this problem.",
        default=1,
        values={"min": 1}, scope=Scope.settings)

    max_points = Integer(
        display_name="Possible points",
        help="Defines the maximum points that the learner can earn.",
        default=1,
        scope=Scope.settings)

    show_points_earned = Boolean(
        display_name="Shows points earned",
        help="Shows points earned",
        default=True,
        scope=Scope.settings)

    show_submission_times = Boolean(
        display_name="Shows submission times",
        help="Shows submission times",
        default=True,
        scope=Scope.settings)

    show_answer = Boolean(
        display_name="Show Answer",
        help="Defines when to show the 'Show/Hide Answer' button",
        default=True,
        scope=Scope.settings)

    #TODO: add comments about scope of these new variables. Why these variables?
    #
    _image_url = String (
        display_name ="image",
        help ="",
        default="",
        scope = Scope.settings)

    _resolver_selection = String(
        display_name = "Resolver Machine",
        help ="",
        default = 'none',
        scope = Scope.content)

    _problem_solver = String(
        display_name = "Problem Solver",
        help = "Select a solver for this problem",
        default = 'none',
        scope = Scope.settings,
        values = [
                    {"display_name": "MatLab", "value": "matlab"},
                    {"display_name": "None", "value": "none"},
                ]
    )

    _question_template = String (
        display_name = "Question Template",
        help = "",
        default = "Given a = [a] and b = [b]. Calculate the sum, difference of a and b.",
        scope = Scope.settings
    )

    _answer_template = Dict(
        display_name="Answer Template",
        help="Teacher has to fill the answer template here!!!",
        default=
            {
                "sum": "[a] + [b]",
                "difference": "[a] - [b]"
            },
        scope=Scope.settings
    )

    _answer_template_string = String(
        display_name="Answer Template",
        help="Teacher has to fill the answer template here!!!",
        default= '''sum = [a] + [b]\ndifference = [a] - [b]''',
        scope=Scope.settings
    )

    _variables = Dict (
        display_name = "Variable List",
        help = "",
        default =
            {
                'a': {'name': 'a',
                'min_value': 1,
                'max_value': 200,
                'type': 'int',
                'decimal_places': 0
                } ,
                'b' :{'name': 'b',
                'min_value': 1.00,
                'max_value': 20.99,
                'type': 'float',
                'decimal_places': 2
                }
            },
        scope = Scope.settings)

    # Default XML string passed to Advanced Editor's value when create an xBlock
    raw_editor_xml_data = '''
    <problem>
        <description>Given a = [a] and b = [b]. Calculate the sum, difference of a and b. </description>
        <image_group>
            <image_url link="http://example.com/image1">Image</image_url>
        </image_group>
        <variable_group>
            <variable name="a" min_value="1" max_value="200" type="integer"/>
            <variable name="b" min_value="1.00" max_value="20.99" type="float" decimal_places="2"/>
        </variable_group>
        <answer_template_group>
            <answer sum = "[a] + [b]" difference = "[a] - [b]">Teacher's answer</answer>
        </answer_template_group>
    </problem>'''

    # This field is to store editor's value to keep for future initilize (student_view, studio_view) of xBlock after edit.
    _raw_editor_xml_data = String(
        display_name="Raw edit",
        help="Raw edit fields value for XML editor",
        default=raw_editor_xml_data,
        scope=Scope.content
    )

    xblock_id = None
    attempt_number = 0
    newly_created_block = True
    has_score = True
    show_in_read_only_mode = True

    editable_fields = ('display_name',
                       '_problem_solver',
                       'max_attempts',
                       'max_points',
                       'show_points_earned',
                       'show_submission_times',
                       'show_answer',
                       '_raw_editor_xml_data'
                       )

    # problem solver info
    resolver_handling = resolver_machine()
    resolver_selection = resolver_handling.getDefaultResolver()
    matlab_server_url = resolver_handling.getDefaultAddress()
    matlab_solver_url = resolver_handling.getDefaultURL()

    # customed global variables
    image_url = ""
    question_template_string = ""
    variables = {}
    _generated_question = ""
    _generated_variables = {}
    student_answer = ""

    # Define current editor mode
    enable_advanced_editor = False  # True: Editor mode, False: Template mode.


    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")


    def student_view(self, context):
        """
        The primary view of the MatlabQuestionXBlock
, shown to students when viewing courses.
        """
        print("## Calling FUNCTION student_view() ##")
        print("## START DEBUG INFO ##")
        print("context = {}".format(context))

        context = context

        if self.xblock_id is None:
            self.xblock_id = unicode(self.location.replace(branch=None, version=None))

        should_disbled = ''

        # generate question from template if necessary

        # self._generated_question, self._generated_variables = matlab_question_service.generate_question_old(self._question_template, self._variables)
        self._generated_question, self._generated_variables = matlab_question_service.generate_question(
            self._question_template, self._variables)

        print("self._generated_question = {}".format(self._generated_question))
        print("self._generated_variables = {}".format(self._generated_variables))

        # load submission data to display the previously submitted result
        submissions = sub_api.get_submissions(self.student_item_key, 1)
        print("previously submitted result = {}".format(submissions))

        if submissions:
            latest_submission = submissions[0]

            # parse the answer
            answer = latest_submission['answer'] # saved "answer information"
            print("previously submitted answer = {}".format(submissions))

            # INCORRECT ???
            # TODO: remove these
            # self._generated_question = answer['generated_question']
            # self.generated_answer = answer['generated_answer']  # teacher's generated answer
            # self.student_answer = answer['student_answer'] # student's submitted answer

            if ('variable_values' in answer): # backward compatibility
                saved_generated_variables = json.loads(answer['variable_values'])
                for var_name, var_value in saved_generated_variables.iteritems():
                    self._generated_variables[var_name] = var_value

            self.attempt_number = latest_submission['attempt_number']
            if (self.attempt_number >= self.max_attempts):
                should_disbled = 'disabled'


        self.serialize_data_to_context(context)

        # Add following fields to context variable
        context['disabled'] = should_disbled
        context['student_answer'] = self.student_answer
        context['image_url'] = self._image_url
        context['attempt_number'] = self.attempt_number_string
        context['point_string'] = self.point_string
        context['question'] = self._generated_question
        context['xblock_id'] = self.xblock_id
        context['show_answer'] = self.show_answer


        frag = Fragment()
        frag.content = loader.render_template('static/html/matlab_question/student_view.html', context)
        frag.add_css(self.resource_string("static/css/question_generator_block.css"))
        frag.add_javascript(self.resource_string("static/js/matlab_question/student_view.js"))
        frag.initialize_js('MatlabQuestionXBlock')

        print("context = {}".format(context))
        print("## End FUNCTION student_view() ##")

        return frag


    def studio_view(self, context):
        """
        Render a form for editing this XBlock (override the StudioEditableXBlockMixin's method)
        """
        print("## Calling FUNCTION studio_view() ##")
        print("## START DEBUG INFO ##")
        print("context = {}".format(context))

        # if the XBlock has been submitted already then disable the studio_edit screen
        location = self.location.replace(branch=None, version=None)  # Standardize the key in case it isn't already
        item_id=unicode(location)

        print("self._variables = {}".format(self._variables))
        print "self._raw_editor_xml_data = {}".format(self._raw_editor_xml_data)

        # Student not yet submit then we can edit the XBlock
        fragment = Fragment()
        context = {'fields': []}
        # Build a list of all the fields that can be edited:
        for field_name in self.editable_fields:
            field = self.fields[field_name]
            assert field.scope in (Scope.content, Scope.settings), (
                "Only Scope.content or Scope.settings fields can be used with "
                "StudioEditableXBlockMixin. Other scopes are for user-specific data and are "
                "not generally created/configured by content authors in Studio."
            )
            field_info = self._make_field_info(field_name, field)
            if field_info is not None:
                context["fields"].append(field_info)


        # self.serialize_data_to_context(context) ??? REMOVE not necessary, remove ???
        context['image_url'] = self._image_url
        # context['resolver_selection'] = self._resolver_selection
        # context['problem_solver'] = self._problem_solver
        context['question_template'] = self._question_template
        context['variables'] = self._variables
        context['answer_template_string'] = self._answer_template_string
        context['is_submitted'] = 'False'
        context['enable_advanced_editor'] = self.enable_advanced_editor
        context['current_editor_mode_name'] = SIMPLE_EDITOR_NAME
        context['next_editor_mode_name'] = ADVANCED_EDITOR_NAME
        if self.enable_advanced_editor:
            context['current_editor_mode_name'] = ADVANCED_EDITOR_NAME
            context['next_editor_mode_name'] = SIMPLE_EDITOR_NAME

        # append xml data for raw xml editor
        context['raw_editor_xml_data'] = self._raw_editor_xml_data

        print("context = {}".format(context))
        print("## End DEBUG INFO ##")

        # fragment.content = loader.render_template('static/html/matlab_question/problem_edit.html', context)
        fragment.content = loader.render_template('static/html/matlab_question/studio_view.html', context)
        fragment.add_css(self.resource_string("static/css/question_generator_block_studio_edit.css"))
        # fragment.add_javascript(loader.load_unicode('static/js/matlab_question/problem_edit.js'))
        fragment.add_javascript(loader.load_unicode('static/js/matlab_question/studio_view.js'))
        fragment.initialize_js('StudioEditableXBlockMixin')

        print("## End FUNCTION studio_view() ##")

        return fragment


    def serialize_data_to_context(self, context):
        """
        Save data to context to re-use later to avoid re-accessing the DBMS
        """
        print("## CALLING FUNCTION serialize_data_to_context() ##")

        print("## BEFORE ADDING FIELDS ##")
        print("context = {}".format(context))
        print("## START DEBUG INFO ##")
        print("self._question_template = {}".format(self._question_template))
        print("self._image_url = {}".format(self._image_url))
        print("self._variables= {}".format(self._variables))
        print("self._generated_variables= {}".format(self._generated_variables))
        # print("self._answer_template= {}".format(self._answer_template))
        print "self._answer_template_string = ", self._answer_template_string


        # Add following fields to context variable
        context['saved_question_template'] = self._question_template
        context['saved_url_image'] = self._image_url
        context['serialized_variables'] = json.dumps(self._variables)
        context['serialized_generated_variables'] = json.dumps(self._generated_variables)
        # context['saved_answer_template'] = self._answer_template  # dict
        context['saved_answer_template'] = self._answer_template_string # string

        # context['saved_resolver_selection'] = self._resolver_selection # Old
        context['saved_resolver_selection'] = self._problem_solver  # use _problem_solver from editable_fields

        print("## AFTER, ADDED FIELDS ##")
        print("context = {}".format(context))
        print("## END DEBUG INFO ##")
        print("## End FUNCTION serialize_data_to_context() ##")


    def deserialize_data_from_context(self, context):
        """
        De-serialize data previously saved to context
        """
        print("## CALLING FUNCTION deserialize_data_from_context() ##")
        print("## START DEBUG INFO ##")

        print("self._question_template = {}".format(self._question_template))
        print("self._image_url = {}".format(self._image_url))
        print("self._variables= {}".format(self._variables))
        print("self._generated_variables= {}".format(self._generated_variables))
        # print("self._answer_template= {}".format(self._answer_template))
        print "self._answer_template_string = ", self._answer_template_string

        print("## BEFORE ##")
        print("context = {}".format(context))

        self.question_template_string = context['saved_question_template']
        self.image_url = context['saved_url_image']
        # self._answer_template = context['saved_answer_template']
        self._answer_template_string = context['saved_answer_template']
        #
        self.variables = json.loads(context['serialized_variables'])
        self._generated_variables = json.loads(context['serialized_generated_variables'])
        self.resolver_selection = context['saved_resolver_selection']   # TODO: update this to new field in Settings tab

        print("## GLOBAL VARIABLES, AFTER: ##")
        print("self._question_template = {}".format(self.question_template_string))
        print("self.image_url = {}".format(self.image_url))
        # print("self._answer_template= {}".format(self._answer_template))
        print "self._answer_template_string = ", self._answer_template_string
        print("self.variables = {}".format(self.variables))
        print("self._variables= {}".format(self._variables))
        print("self._generated_variables = {}".format(self._generated_variables))
        print("self.resolver_selection = {}".format(self.resolver_selection))
        print("## End DEBUG INFO ##")
        print("## End FUNCTION deserialize_data_from_context() ##")


    def load_data_from_dbms(self):
        """
        Load question template data from MySQL
        """

        if self.xblock_id is None:
            self.xblock_id = unicode(self.location.replace(branch=None, version=None))

        self.question_template_string, self.image_url, self.resolver_selection, self.variables, self._answer_template_string = qgb_db_service.fetch_question_template_data(self.xblock_id)


    @XBlock.json_handler
    def student_submit(self, data, suffix=''):
        """
        AJAX handler for Submit button
        """

        print("## CALLING FUNCTION student_submit() ##")
        print("## START DEBUG INFO ##")
        print("data = {}".format(data))

        self.deserialize_data_from_context(data)

        points_earned = 0

        # TODO generate the teacher's answer
        # Generate answer for this submission
        # generated_answer = matlab_question_service.generate_answer(self._generated_variables, self._answer_template)
        # print("generated_answer = {}".format(generated_answer))

        generated_answer = matlab_question_service.generate_answer_string(self._generated_variables, self._answer_template_string)
        print "generated_answer = ", generated_answer

        student_answer = data['student_answer']
        # save the submission
        submission_data = {
            'generated_question': data['saved_generated_question'],
            'student_answer': student_answer,
            'generated_answer': generated_answer,
            'variable_values': data['serialized_generated_variables']
        }
        print("submission_data = {}".format(submission_data))

        # call matlab
        evaluation_result = self.resolver_handling.syncCall(self.resolver_selection, generated_answer, student_answer )
        #evaluation_result = matlab_service.evaluate_matlab_answer(self.matlab_server_url, self.matlab_solver_url, generated_answer, student_answer)

        if evaluation_result == True:
            points_earned = self.max_points

        submission = sub_api.create_submission(self.student_item_key, submission_data)
        sub_api.set_score(submission['uuid'], points_earned, self.max_points)

        submit_result = {}
        submit_result['point_string'] = self.point_string

        # disable the "Submit" button once the submission attempts reach max_attemps value
        self.attempt_number = submission['attempt_number']
        submit_result['attempt_number'] = self.attempt_number_string
        if (self.attempt_number >= self.max_attempts):
            submit_result['submit_disabled'] = 'disabled'
        else:
            submit_result['submit_disabled'] = ''

        print("## End FUNCTION student_submit() ##")

        return submit_result

    @XBlock.json_handler
    def fe_submit_studio_edits(self, data, suffix=''):
        """
        AJAX handler for studio edit submission, two edit modes:

        1. Basic template (Default mode)
        2. Advanced editor

        """

        print("## Calling FUNCTION fe_submit_studio_edits() ###")
        print("## DEBUG INFO ###")
        print("data fields: {}".format(data))
        print("### editor updated xml_data: ###")
        print(data['raw_editor_xml_data'])

        print("BEFORE SAVE, self.enable_advanced_editor = {}".format(self.enable_advanced_editor))
        print("targeted mode, data['enable_advanced_editor'] = {}".format(data['enable_advanced_editor']))

        print("self.raw_editor_xml_data = {}".format(self.raw_editor_xml_data))
        print("Data type of data['answer_template'] = {}".format(type(data['answer_template'])))

        if self.xblock_id is None:
            self.xblock_id = unicode(self.location.replace(branch=None, version=None))

        if data['enable_advanced_editor'] == 'False':
            print("### IN CASE self.enable_advanced_editor == False: ###")
            # process problem edit via UI template
            updated_question_template = data['question_template']
            updated_url_image = data['image_url']
            # updated_resolver_selection = data['resolver_selection']
            updated_variables = data['variables']
            updated_answer_template = data['answer_template']

            #qgb_db_service.update_question_template(self.xblock_id, updated_question_template, updated_url_image, updated_resolver_selection, updated_variables, updated_answer_template)

            print("BEFORE, self._answer_template_string = ")
            print(self._answer_template_string)
            print("Data type of self._answer_template_string = {}".format(type(self._answer_template_string)))
            print("Data type of updated_answer_template = {}".format(type(updated_answer_template)))

            # Update XBlock's values
            self.enable_advanced_editor = False
            self.question_template_string = updated_question_template
            self.image_url = updated_url_image
            # self.resolver_selection = updated_resolver_selection
            self.variables = updated_variables
            self._answer_template_string = updated_answer_template

            print("AFTER, self._answer_template_string = ")
            print(self._answer_template_string)
            print("Data type of self._answer_template_string = {}".format(type(self._answer_template_string)))

            setattr(self, '_image_url', updated_url_image)
            # setattr(self, '_resolver_selection', updated_resolver_selection)
            setattr(self, '_question_template', updated_question_template)
            # setattr(self, '_answer_template', updated_answer_template)
            setattr(self, '_answer_template_string', updated_answer_template)
            setattr(self, '_variables', updated_variables)

            # build xml string for problem raw edit fields,
            # then update value to field '_raw_editor_xml_data' for editor
            input_data = {
                'question_template': self.question_template_string,
                'image_url': self.image_url,
                'variables': self.variables,
                'answer_template': self._answer_template_string
            }

            # Convert dict data to xml
            xml_string = xml_helper.convert_data_from_dict_to_xml(input_data)

            # Finally, update value for field attribute
            setattr(self, '_raw_editor_xml_data', xml_string)

        elif data['enable_advanced_editor'] == 'True':
            print("### IN CASE self.enable_advanced_editor == True: ###")
            # Process raw edit
            updated_xml_string = data['raw_editor_xml_data']

            # Extract data fields from xml string
            raw_edit_data = xml_helper.extract_data_from_xmlstring_to_dict(updated_xml_string)

            # TODO: then save to DB model? To remove this line
            # qgb_db_service.update_question_template(self.xblock_id, updated_question_template, updated_url_image, updated_resolver_selection, updated_variables, updated_answer_template)

            updated_question_template = raw_edit_data['question_template']
            updated_url_image = raw_edit_data['image_url']
            updated_variables = raw_edit_data['variables']
            # get only one firt answer for now. TODO: update to support multi-answers attributes for multiple solutions
            updated_answer_template_dict = raw_edit_data['answer_template'][1]
            # updated_resolver_selection = data['problem_solver']

            # convert answer dict to string
            updated_answer_template = xml_helper.convert_answer_template_dict_to_string(updated_answer_template_dict)


            print("BEFORE, self._answer_template_string = ")
            print(self._answer_template_string)

            print("Data type of self._answer_template_string = {}".format(type(self._answer_template_string)))
            print("Data type of updated_answer_template = {}".format(type(updated_answer_template)))

            # "refresh" XBlock's values
            # update values to global variables
            self.enable_advanced_editor = True
            self.question_template_string = updated_question_template
            self.image_url = updated_url_image
            self.variables = updated_variables
            # setattr(self, '_answer_template', updated_answer_template)
            self._answer_template_string = updated_answer_template
            # self.resolver_selection = updated_resolver_selection

            print("AFTER, self._answer_template_string = ")
            print(self._answer_template_string)

            print("Data type of self._answer_template_string = {}".format(type(self._answer_template_string)))

            # update values to global fields
            setattr(self, '_question_template', updated_question_template)
            setattr(self, '_image_url', updated_url_image)
            # setattr(self, '_answer_template', updated_answer_template)
            setattr(self, '_answer_template_string', updated_answer_template)
            setattr(self, '_variables', updated_variables)
            # setattr(self, '_resolver_selection', updated_resolver_selection)

            # update raw edit fields data
            self.raw_editor_xml_data = updated_xml_string
            setattr(self, '_raw_editor_xml_data', updated_xml_string)

        print("AFTER SAVE, self.raw_editor_xml_data = {}".format(self.raw_editor_xml_data))

        # copy from StudioEditableXBlockMixin (can not call parent method)
        values = {}  # dict of new field values we are updating
        to_reset = []  # list of field names to delete from this XBlock
        for field_name in self.editable_fields:
            field = self.fields[field_name]
            if field_name in data['values']:
                if isinstance(field, JSONField):
                    values[field_name] = field.from_json(data['values'][field_name])
                else:
                    raise JsonHandlerError(400, "Unsupported field type: {}".format(field_name))
            elif field_name in data['defaults'] and field.is_set_on(self):
                to_reset.append(field_name)

        self.clean_studio_edits(values)
        validation = Validation(self.scope_ids.usage_id)

        # We cannot set the fields on self yet, because even if validation fails, studio is going to save any changes we
        # make. So we create a "fake" object that has all the field values we are about to set.
        preview_data = FutureFields(
            new_fields_dict=values,
            newly_removed_fields=to_reset,
            fallback_obj=self
        )

        self.validate_field_data(validation, preview_data)
        print("preview_data fields: {}".format(preview_data))
        print("## End DEBUG INFO ###")

        if validation:
            for field_name, value in values.iteritems():
                setattr(self, field_name, value)
            for field_name in to_reset:
                self.fields[field_name].delete_from(self)
            return {'result': 'success'}
        else:
            raise JsonHandlerError(400, validation.to_json())


    @property
    def point_string(self):
        if self.show_points_earned:
            score = sub_api.get_score(self.student_item_key)
            if score != None:
                return str(score['points_earned']) + ' / ' + str(score['points_possible']) + ' point(s)'

        return str(self.max_points) + ' point(s) possible'


    @property
    def attempt_number_string(self):
        if (self.show_submission_times):
            return "You have submitted " + str(self.attempt_number) + "/" + str(self.max_attempts) + " time(s)"

        return ""


    @XBlock.json_handler
    def show_answer_handler(self, data, suffix=''):
        """
        AJAX handler for "Show/Hide Answer" button
        """
        print("## CALLING FUNCTION show_answer_handler() ##")
        print("## START DEBUG INFO ##")
        print("data = {}".format(data))

        self.deserialize_data_from_context(data)

        # generated_answer = matlab_question_service.generate_answer(self._generated_variables, self._answer_template)
        generated_answer = matlab_question_service.generate_answer_string(self._generated_variables, self._answer_template_string)

        print("generated_answer = {}".format(generated_answer))
        print("## START DEBUG INFO ##")
        print("## END FUNCTION show_answer_handler() ##")

        return {
            'generated_answer': generated_answer
        }


    # TO-DO: change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("MatlabQuestionXBlock",
             """<question_generator_block/>
             """),
            ("Multiple MatlabQuestionXBlock",
             """<vertical_demo>
                <question_generator_block/>
                <question_generator_block/>
                <question_generator_block/>
                </vertical_demo>
             """),
        ]
