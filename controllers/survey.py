# -*- coding: utf-8 -*-

"""
    survey - Assessment Data Analysis Tool

    @author: Graeme Foster <graeme at acm dot org>

    For more details see the blueprint at:
    http://eden.sahanafoundation.org/wiki/BluePrint/SurveyTool/ADAT
"""

"""
    @todo: open template from the dataTables into the section tab not update
    @todo: in the pages that add a link to a template make the combobox display the label not the numbers
    @todo: restrict the deletion of a template to only those with status Pending

"""

import sys
sys.path.append("applications/%s/modules/s3" % request.application)
try:
    from cStringIO import StringIO    # Faster, where available
except:
    from StringIO import StringIO

import base64
import math

from gluon.contenttype import contenttype
from gluon.languages import read_dict, write_dict

from s3survey import S3AnalysisPriority, \
                     survey_question_type, \
                     survey_analysis_type, \
                     DataMatrix, MatrixElement, \
                     S3QuestionTypeOptionWidget, \
                     survey_T

module = request.controller
prefix = request.controller
resourcename = request.function

if not deployment_settings.has_module(prefix):
    raise HTTP(404, body="Module disabled: %s" % prefix)

s3_menu(module)

def index():

    """ Module's Home Page """

    module_name = deployment_settings.modules[prefix].name_nice
    response.title = module_name
    return dict(module_name=module_name)

def template():

    """ RESTful CRUD controller """

    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]
    s3 = response.s3

    def prep(r):
        if r.component and r.component_name == "translate":
            table = db["survey_translate"]
            # list existing translations and allow the addition of a new translation
            if r.component_id == None:
                table.file.readable = False
                table.file.writable = False
            # edit the selected translation
            else:
                table.language.writable = False
                table.code.writable = False
            # remove CRUD generated buttons in the tabs
            s3mgr.configure(table,
                            deletable=False,
                           )
        else:
            s3_action_buttons(r)
            query = (r.table.status == 1) # Status of Pending
            rows = db(query).select(r.table.id)
            try:
                s3.actions[1]["restrict"].extend(str(row.id) for row in rows)
            except KeyError: # the restrict key doesn't exist
                s3.actions[1]["restrict"] = [str(row.id) for row in rows]
            except IndexError: # the delete buttons doesn't exist
                pass
            s3mgr.configure(r.tablename,
                            orderby = "%s.status" % r.tablename,
                            create_next = URL(c="survey", f="template"),
                            update_next = URL(c="survey", f="template"),
                            )
        return True

     # Post-processor
    def postp(r, output):
        if r.component:
            template_id = request.args[0]
            if r.component_name == "section":
                # Add the section select widget to the form
                sectionSelect = s3.survey_section_select_widget(template_id)
                output.update(form = sectionSelect)
                return output
            elif r.component_name == "translate":
                s3_action_buttons(r)
                s3.actions.append(
                                   dict(label=str(T("Download")),
                                        _class="action-btn",
                                        url=URL(c=module,
                                                f="templateTranslateDownload",
                                                args=["[id]"])
                                       ),
                                  )
                s3.actions.append(
                           dict(label=str(T("Upload")),
                                _class="action-btn",
                                url=URL(c=module,
                                        f="template",
                                        args=[template_id,"translate","[id]"])
                               ),
                          )
                return output


        # Add a button to show what the questionnaire looks like
#        s3_action_buttons(r)
#        s3.actions = s3.actions + [
#                               dict(label=str(T("Display")),
#                                    _class="action-btn",
#                                    url=URL(c=module,
#                                            f="templateRead",
#                                            args=["[id]"])
#                                   ),
#                              ]

        # Add some highlighting to the rows
        query = (r.table.status == 3) # Status of closed
        rows = db(query).select(r.table.id)
        s3.dataTableStyleDisabled = [str(row.id) for row in rows]
        s3.dataTableStyleWarning = [str(row.id) for row in rows]
        query = (r.table.status == 1) # Status of Pending
        rows = db(query).select(r.table.id)
        s3.dataTableStyleAlert = [str(row.id) for row in rows]
        query = (r.table.status == 4) # Status of Master
        rows = db(query).select(r.table.id)
        s3.dataTableStyleWarning.extend(str(row.id) for row in rows)
        return output

    if request.ajax:
        post = request.post_vars
        action = post.get("action")
        template_id = post.get("parent_id")
        section_id = post.get("section_id")
        section_text = post.get("section_text")
        if action == "section" and template_id != None:
            id = db.survey_section.insert(name=section_text,
                                          template_id=template_id,
                                          cloned_section_id=section_id)
            if id == None:
                print "Failed to insert record"
            return

    response.s3.prep = prep

    response.s3.postp = postp
    rheader = response.s3.survey_template_rheader
    # remove CRUD generated buttons in the tabs
    s3mgr.configure(tablename,
                    listadd=False,
                    deletable=False,
                   )
    output = s3_rest_controller(prefix, resourcename, rheader=rheader)

    return output

def templateRead():
    # Load Model
    prefix = "survey"
    resourcename = "template"
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    s3 = response.s3
    crud_strings = s3.crud_strings[tablename]
    if "vars" in request and len(request.vars) > 0:
        dummy, template_id = request.vars.viewing.split(".")
    else:
        template_id = request.args[0]

    def postp(r, output):
        if r.interactive:
            template_id = r.id
            form = s3.survey_buildQuestionnaireFromTemplate(template_id)
            output["items"] = None
            output["form"] = None
            output["item"] = form
            output["title"] = crud_strings.title_question_details
            return output

    # remove CRUD generated buttons in the tabs
    s3mgr.configure(tablename,
                    listadd=False,
                    editable=False,
                    deletable=False,
                   )

    response.s3.postp = postp
    r = s3mgr.parse_request(prefix, resourcename, args=[template_id])
    output  = r(method = "read", rheader=s3.survey_template_rheader)
    del output["list_btn"] # Remove the list button
    return output

def templateSummary():
    # Load Model
    prefix = "survey"
    resourcename = "template"
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    s3 = response.s3
    crud_strings = s3.crud_strings[tablename]

    def postp(r, output):
        if r.interactive:
            if "vars" in request and len(request.vars) > 0:
                dummy, template_id = request.vars.viewing.split(".")
            else:
                template_id = r.id
            form = s3.survey_build_template_summary(template_id)
            output["items"] = form
            output["sortby"] = [[0,"asc"]]
            output["title"] = crud_strings.title_analysis_summary
            output["subtitle"] = crud_strings.subtitle_analysis_summary
            return output

    # remove CRUD generated buttons in the tabs
    s3mgr.configure(tablename,
                    listadd=False,
                    deletable=False,
                   )

    response.s3.postp = postp
    output = s3_rest_controller(prefix,
                                resourcename,
                                method = "list",
                                rheader=s3.survey_template_rheader
                               )
    response.s3.actions = None
    return output

def templateTranslateDownload():
    # Load Model
    prefix = "survey"
    resourcename = "translate"
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)

    try:
        import xlwt
    except ImportError:
        redirect(URL(c="survey",
                     f="templateTranslation",
                     args=[],
                     vars = {}))
    s3 = response.s3
    record = s3.survey_getTranslation(request.args[0])
    if record == None:
        redirect(URL(c="survey",
                     f="templateTranslation",
                     args=[],
                     vars = {}))
    code = record.code
    language = record.language
    lang_fileName = "applications/%s/languages/%s.py" % \
                                    (request.application, code)
    try:
        strings = read_dict(lang_fileName)
    except:
        strings = dict()
    template_id = record.template_id
    template = s3.survey_getTemplate(template_id)
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet(language)
    output = StringIO()
    qstnList = s3.survey_getAllQuestionsForTemplate(template_id)
    original = {}
    original[template["name"]] = True
    if template["description"] != "":
        original[template["description"]] = True
    for qstn in qstnList:
        original[qstn["name"]] = True
        widgetObj = survey_question_type[qstn["type"]](question_id = qstn["qstn_id"])
        if isinstance(widgetObj, S3QuestionTypeOptionWidget):
            optionList = widgetObj.getList()
            for option in optionList:
                original[option] = True
    sections = s3.survey_getAllSectionsForTemplate(template_id)
    for section in sections:
        original[section["name"]]=True
        section_id = section["section_id"]
        layoutRules = s3.survey_getQstnLayoutRules(template_id, section_id)
        layoutStr = str(layoutRules)
        posn = layoutStr.find("heading")
        while posn != -1:
            start = posn + 11
            end = layoutStr.find("}", start)
            original[layoutStr[start:end]] = True
            posn = layoutStr.find("heading", end)

    row = 0
    sheet.write(row,
                0,
                unicode("Original")
               )
    sheet.write(row,
                1,
                unicode("Translation")
               )
    originalList = original.keys()
    originalList.sort()
    for text in originalList:
        row += 1
        original = unicode(text)
        sheet.write(row,
                    0,
                    original
                   )
        if (original in strings):
            sheet.write(row,
                        1,
                        strings[original]
                       )

    book.save(output)
    output.seek(0)
    response.headers["Content-Type"] = contenttype(".xls")
    filename = "%s.xls" % code
    response.headers["Content-disposition"] = "attachment; filename=\"%s\"" % filename
    return output.read()

def series():
    """ RESTful CRUD controller """
    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]
    response.s3.survey_answerlist_dataTable_pre()

    def prep(r):
        if r.interactive:
            if r.method == "create":
                allTemplates = response.s3.survey_getAllTemplates()
                if len(allTemplates) == 0:
                    session.warning = T("You need to create a template before you can create a series")
                    redirect(URL(c="survey",
                             f="template",
                             args=[],
                             vars = {}))
            if r.id and (r.method == "update"):
                table.template_id.writable = False
        return True

    def postp(r, output):
        if request.ajax == True and r.method == "read":
            return output["item"]
        s3 = response.s3
        if r.component_name == None:
            s3.survey_serieslist_dataTable_post(r)
        elif r.component_name == "complete":
            if r.method == "update":
                if r.http == "GET":
                    form = s3.survey_buildQuestionnaireFromSeries(r.id,
                                                                  r.component_id)
                    output["form"] = form
                elif r.http == "POST":
                    if "post_vars" in request and len(request.post_vars) > 0:
                        id = s3.survey_save_answers_for_series(r.id,
                                                               r.component_id, # Update
                                                               request.post_vars)
                        response.flash = s3.crud_strings["survey_complete"].msg_record_modified
            else:
                s3.survey_answerlist_dataTable_post(r)
        return output

    # Remove CRUD generated buttons in the tabs
    s3mgr.configure("survey_series",
                    deletable = False,)
    s3mgr.configure("survey_complete",
                    listadd=False,
                    deletable=False)
    response.s3.prep = prep
    response.s3.postp = postp
    output = s3_rest_controller(prefix,
                                resourcename,
                                rheader=response.s3.survey_series_rheader)
    return output

def series_export_formatted():
    prefix = "survey"
    resourcename = "series"
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    crud_strings = response.s3.crud_strings[tablename]

    try:
        import xlwt
    except ImportError:
        output = s3_rest_controller(prefix,
                                resourcename,
                                rheader=response.s3.survey_series_rheader)
        return output

    ######################################################################
    #
    # Get the data
    # ============
    # * The sections within the template
    # * The layout rules for each question
    ######################################################################
    # Check that the series_id has been passed in
    if len(request.args) != 1:
        output = s3_rest_controller(prefix,
                                    resourcename,
                                    rheader=response.s3.survey_series_rheader)
        return output
    if "translationLanguage" in request.post_vars:
        lang = request.post_vars.translationLanguage
        if lang == "Default":
            langDict = dict()
        else:
            try:
                lang_fileName = "applications/%s/uploads/survey/translations/%s.py" % (request.application, lang)
                langDict = read_dict(lang_fileName)
            except:
                langDict = dict()
    series_id = request.args[0]
    sectionList = response.s3.survey_getAllSectionsForSeries(series_id)
    layout = {}
    for section in sectionList:
        sectionName = section["name"]
        rules =  response.s3.survey_getQstnLayoutRules(section["template_id"],
                                                       section["section_id"]
                                                      )
        layout[sectionName] = rules

    ######################################################################
    #
    # Store the questions into a matrix based on the layout and the space
    # required for each question - for example an option question might
    # need one row for each possible option, and if this is in a layout
    # then the position needs to be recorded carefully...
    #
    ######################################################################
    def processRule(series_id, rules, row, col,
                    matrix, matrixAnswer, action="rows"):
        startcol = col
        startrow = row
        endcol = col
        endrow = row
        nextrow = row
        nextcol = col
        for element in rules:
            if action == "rows":
                row = endrow
                col = startcol
            elif action == "columns":
                row = startrow
                if endcol == 0:
                    col = 0
                else:
                    col = endcol+1
            # If the rule is a list then step through each element
            if isinstance(element,list):
                if action == "rows":
                    tempAction = "columns"
                else:
                    tempAction = "rows"
                (endrow, endcol) = processRule(series_id, element, row, col,
                                               matrix, matrixAnswer, tempAction)
            elif isinstance(element,dict):
                (endrow, endcol) = processDict(series_id, element, row, col,
                                               matrix, matrixAnswer, action)
            else:
                (endrow, endcol) = addData(element, row, col,
                                           matrix, matrixAnswer)
            if endrow > nextrow:
                nextrow = endrow
            if endcol > nextcol:
                nextcol = endcol
        return (nextrow, nextcol)

    def processDict(series_id, rules, row, col,
                    matrix, matrixAnswer, action="rows"):
        startcol = col
        startrow = row
        nextrow = row
        nextcol = col
        for (key, value) in rules.items():
            if (key == "heading"):
                cell = MatrixElement(row,col,value, style="styleSubHeader")
                cell.merge(horizontal=1)
                try:
                    matrix.addElement(cell)
                except Exception as msg:
                    print msg
                    return (row,col)
                endrow = row + 1
                endcol = col + 2
            elif (key == "rows") or (key == "columns"):
                (endrow, endcol) = processRule(series_id, value, row, col,
                                               matrix, matrixAnswer, action=key)
            else:
                ## Unknown key
                continue
            if action == "rows":
                row = startrow
                col = endcol + 1 # Add a blank column
            elif action == "columns":
                row = endrow
                col = startcol
            if endrow > nextrow:
                nextrow = endrow
            if endcol > nextcol:
                nextcol = endcol
        return (nextrow, nextcol)

    def addData(qstn, row, col, matrix, matrixAnswer):
        question = response.s3.survey_getQuestionFromCode(qstn, series_id)
        if question == {}:
            return (row,col)
        widgetObj = survey_question_type[question["type"]](question_id = question["qstn_id"])
        try:
            (endrow, endcol) = widgetObj.writeToMatrix(matrix,
                                                       row,
                                                       col,
                                                       answerMatrix=matrixAnswer,
                                                       langDict = langDict
                                                      )
        except Exception as msg:
            print msg
            return (row,col)
        if question["type"] == "Grid":
            matrix.boxRange(row, col, endrow-1, endcol-1)
        return (endrow, endcol)

    row = 0
    col = 0
    matrix = DataMatrix()
    matrixAnswers = DataMatrix()
    template = response.s3.survey_getTemplateFromSeries(series_id)
    series = response.s3.survey_getSeries(series_id)
    logo = os.path.join(request.folder,
                        "static",
                        "img",
                        "logo",
                        series.logo
                        )
    if os.path.exists(logo) and os.path.isfile(logo):
        cell = MatrixElement(0,col,"", style=["styleText"])
        cell.merge(vertical=2)
        matrix.addElement(cell)
        col = 2
        row += 1
    else:
        logo = None
    title = "%s (%s)" % (series.name, template.name)
    title = survey_T(title, langDict)
    cell = MatrixElement(0, col, title, style="styleHeader")
    cell.merge(vertical=1, horizontal=4)
    matrix.addElement(cell)
    row += 2

    for section in sectionList:
        col = 0
        row += 1
        rules =  layout[section["name"]]
        cell = MatrixElement(row, col, survey_T(section["name"], langDict),
                             style="styleHeader")
        try:
            matrix.addElement(cell)
        except Exception as msg:
            print msg
        row += 1
        startrow = row
        (row, col) = processRule(series_id, rules, row, col, matrix, matrixAnswers)
        matrix.boxRange(startrow, 0, row, col-1)

    ######################################################################
    #
    # Now take the matrix data type and generate a spreadsheet from it
    #
    ######################################################################
    import math
    def wrapText(sheet, cell, style):
        row = cell.row
        col = cell.col
        try:
            text = unicode(cell.text)
        except:
            text = cell.text
        width = 16
        # Wrap text and calculate the row width and height
        characters_in_cell = float(width-2)
        twips_per_row = 255 #default row height for 10 point font
        if cell.merged():
            sheet.write_merge(cell.row,
                              cell.row + cell.mergeV,
                              cell.col,
                              cell.col + cell.mergeH,
                              text,
                              style
                             )
            rows = math.ceil((len(text) / characters_in_cell) / (1 + cell.mergeH))
        else:
            sheet.write(cell.row,
                        cell.col,
                        text,
                        style
                       )
            rows = math.ceil(len(text) / characters_in_cell)
        new_row_height = int(rows * twips_per_row)
        new_col_width = width * COL_WIDTH_MULTIPLIER
        if sheet.row(row).height < new_row_height:
            sheet.row(row).height = new_row_height
        if sheet.col(col).width < new_col_width:
            sheet.col(col).width = new_col_width

    def mergeStyles(listTemplate, styleList):
        """
            Take a list of styles and return a single style object with
            all the differences from a newly created object added to the
            resultant style.
        """
        if len(styleList) == 0:
            finalStyle = xlwt.XFStyle()
        elif len(styleList) == 1:
            finalStyle = listTemplate[styleList[0]]
        else:
            zeroStyle = xlwt.XFStyle()
            finalStyle = xlwt.XFStyle()
            for i in range(0,len(styleList)):
                finalStyle = mergeObjectDiff(finalStyle,
                                             listTemplate[styleList[i]],
                                             zeroStyle)
        return finalStyle

    def mergeObjectDiff(baseObj, newObj, zeroObj):
        """
            function to copy all the elements in newObj that are different from
            the zeroObj and place them in the baseObj
        """
        elementList = newObj.__dict__
        for (element, value) in elementList.items():
            try:
                baseObj.__dict__[element] = mergeObjectDiff(baseObj.__dict__[element],
                                                            value,
                                                            zeroObj.__dict__[element])
            except:
                if zeroObj.__dict__[element] != value:
                    baseObj.__dict__[element] = value
        return baseObj

    COL_WIDTH_MULTIPLIER = 240
    book = xlwt.Workbook(encoding="utf-8")
    output = StringIO()

    protection = xlwt.Protection()
    protection.cell_locked = 1
    noProtection = xlwt.Protection()
    noProtection.cell_locked = 0

    borders = xlwt.Borders()
    borders.left = xlwt.Borders.THIN
    borders.right = xlwt.Borders.THIN
    borders.top = xlwt.Borders.THIN
    borders.bottom = xlwt.Borders.THIN

    borderTL = xlwt.Borders()
    borderTL.left = xlwt.Borders.DOUBLE
    borderTL.top = xlwt.Borders.DOUBLE

    borderT = xlwt.Borders()
    borderT.top = xlwt.Borders.DOUBLE

    borderL = xlwt.Borders()
    borderL.left = xlwt.Borders.DOUBLE

    borderTR = xlwt.Borders()
    borderTR.right = xlwt.Borders.DOUBLE
    borderTR.top = xlwt.Borders.DOUBLE

    borderR = xlwt.Borders()
    borderR.right = xlwt.Borders.DOUBLE

    borderBL = xlwt.Borders()
    borderBL.left = xlwt.Borders.DOUBLE
    borderBL.bottom = xlwt.Borders.DOUBLE

    borderB = xlwt.Borders()
    borderB.bottom = xlwt.Borders.DOUBLE

    borderBR = xlwt.Borders()
    borderBR.right = xlwt.Borders.DOUBLE
    borderBR.bottom = xlwt.Borders.DOUBLE

    alignBase = xlwt.Alignment()
    alignBase.horz = xlwt.Alignment.HORZ_LEFT
    alignBase.vert = xlwt.Alignment.VERT_TOP

    alignWrap = xlwt.Alignment()
    alignWrap.horz = xlwt.Alignment.HORZ_LEFT
    alignWrap.vert = xlwt.Alignment.VERT_TOP
    alignWrap.wrap = xlwt.Alignment.WRAP_AT_RIGHT

    shadedFill = xlwt.Pattern()
    shadedFill.pattern = xlwt.Pattern.SOLID_PATTERN
    shadedFill.pattern_fore_colour = 0x16 # 25% Grey
    shadedFill.pattern_back_colour = 0x08 # Black

    styleTitle =  xlwt.XFStyle()
    styleTitle.font.height = 0x0140 # 320 twips, 16 points
    styleTitle.font.bold = True
    styleTitle.alignment = alignBase
    styleHeader = xlwt.XFStyle()
    styleHeader.font.height = 0x00F0 # 240 twips, 12 points
    styleHeader.font.bold = True
    styleHeader.alignment = alignBase
    styleSubHeader = xlwt.XFStyle()
    styleSubHeader.font.bold = True
    styleSubHeader.alignment = alignWrap
    styleText = xlwt.XFStyle()
    styleText.protection = protection
    styleText.alignment = alignWrap
    styleInstructions = xlwt.XFStyle()
    styleInstructions.font.height = 0x00B4 # 180 twips, 9 points
    styleInstructions.font.italic = True
    styleInstructions.protection = protection
    styleInstructions.alignment = alignWrap
    styleBox = xlwt.XFStyle()
    styleBox.borders = borders
    styleBox.protection = noProtection
    styleInput = xlwt.XFStyle()
    styleInput.borders = borders
    styleInput.protection = noProtection
    styleInput.pattern = shadedFill
    boxL = xlwt.XFStyle()
    boxL.borders = borderL
    boxT = xlwt.XFStyle()
    boxT.borders = borderT
    boxR = xlwt.XFStyle()
    boxR.borders = borderR
    boxB = xlwt.XFStyle()
    boxB.borders = borderB
    styleList = {}
    styleList["styleTitle"] = styleTitle
    styleList["styleHeader"] = styleHeader
    styleList["styleSubHeader"] = styleSubHeader
    styleList["styleText"] = styleText
    styleList["styleInstructions"] = styleInstructions
    styleList["styleInput"] = styleInput
    styleList["boxL"] = boxL
    styleList["boxT"] = boxT
    styleList["boxR"] = boxR
    styleList["boxB"] = boxB

    sheet1 = book.add_sheet(T("Assessment"))
    sheetA = book.add_sheet(T("Metadata"))
    for cell in matrix.matrix.values():
        if cell.joined():
            continue
        style = mergeStyles(styleList, cell.styleList)
        if (style.alignment.wrap == style.alignment.WRAP_AT_RIGHT):
            # get all the styles from the joined cells
            # and merge these styles in.
            joinedStyles = matrix.joinedElementStyles(cell)
            joinedStyle =  mergeStyles(styleList, joinedStyles)
            try:
                wrapText(sheet1, cell, joinedStyle)
            except:
                pass
        else:
            if cell.merged():
                # get all the styles from the joined cells
                # and merge these styles in.
                joinedStyles = matrix.joinedElementStyles(cell)
                joinedStyle =  mergeStyles(styleList, joinedStyles)
                sheet1.write_merge(cell.row,
                                   cell.row + cell.mergeV,
                                   cell.col,
                                   cell.col + cell.mergeH,
                                   unicode(cell.text),
                                   joinedStyle
                                   )
            else:
                sheet1.write(cell.row,
                             cell.col,
                             unicode(cell.text),
                             style
                             )

    sheetA.write(0, 0, "Question Code")
    sheetA.write(0, 1, "Response Count")
    sheetA.write(0, 2, "Values")
    sheetA.write(0, 3, "Cell Address")
    for cell in matrixAnswers.matrix.values():
        style = mergeStyles(styleList, cell.styleList)
        sheetA.write(cell.row,
                     cell.col,
                     unicode(cell.text),
                     style
                    )

    if logo != None:
        sheet1.insert_bitmap(logo, 0, 0)

    sheet1.protect = True
    sheetA.protect = True
    for i in range(26):
        sheetA.col(i).width = 0
    sheetA.write(0,
                 26,
                 unicode(T("Please do not remove this sheet")),
                 styleHeader
                )
    sheetA.col(26).width = 12000
    book.save(output)
    output.seek(0)
    response.headers["Content-Type"] = contenttype(".xls")
    seriesName = response.s3.survey_getSeriesName(series_id)
    filename = "%s.xls" % seriesName
    response.headers["Content-disposition"] = "attachment; filename=\"%s\"" % filename
    return output.read()

def completed_chart():
    """ RESTful CRUD controller

        Allows the user to display all the data from the selected question
        in a simple chart. If the data is numeric then a histogram will be
        drawn if it is an option type then a pie chart, although the type of
        chart drawn is managed by the analysis widget.
    """
    # Load Model
    prefix = "survey"
    resourcename = "series"
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    if "series_id" in request.vars:
        seriesID = request.vars.series_id
    else:
        return "Programming Error: Series ID missing"
    if "question_id" in request.vars:
        qstnID = request.vars.question_id
    else:
        return "Programming Error: Question ID missing"
    if "type" in request.vars:
        type = request.vars.type
    else:
        return "Programming Error: Question Type missing"
    getAnswers = response.s3.survey_getAllAnswersForQuestionInSeries
    answers = getAnswers(qstnID, seriesID)
    analysisTool = survey_analysis_type[type](qstnID, answers)
    qstnName = analysisTool.qstnWidget.question.name
    image = analysisTool.drawChart(output="png")
    return image

def section():
    """ RESTful CRUD controller """
    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]

    def prep(r):
        s3mgr.configure(r.tablename,
                        deletable = False,
                        orderby = r.tablename+".posn",
                        )
        return True

     # Post-processor
    def postp(r, output):
        """ Add the section select widget to the form """
        try:
            template_id = int(request.args[0])
        except:
            template_id = None
        sectionSelect = response.s3.survey_section_select_widget(template_id)
        output["sectionSelect"] = sectionSelect
        return output


    response.s3.prep = prep
    response.s3.postp = postp

    rheader = response.s3.survey_section_rheader
    output = s3_rest_controller(prefix, resourcename, rheader=rheader)
    return output



def question():
    """ RESTful CRUD controller """
    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]

    def prep(r):
        s3mgr.configure(r.tablename,
                        orderby = r.tablename+".posn",
                        )
        return True

     # Post-processor
    def postp(r, output):
        return output


    response.s3.prep = prep
    response.s3.postp = postp

    rheader = response.s3.survey_section_rheader
    output = s3_rest_controller(prefix, resourcename, rheader=rheader)
    return output

def question_list():
    """ RESTful CRUD controller """
    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]

    output = s3_rest_controller(prefix, resourcename)
    return output

def formatter():
    """ RESTful CRUD controller """
    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]

    output = s3_rest_controller(prefix, resourcename)
    return output

def question_metadata():
    """ RESTful CRUD controller """
    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]

    output = s3_rest_controller(prefix, resourcename)
    return output

def newAssessment():
    """ RESTful CRUD controller """
    # Load Model
    prefix = "survey"
    resourcename = "complete"
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]
    s3 = response.s3

    def prep(r):
        if r.interactive:
            if "viewing" in request.vars:
                dummy, series_id = request.vars.viewing.split(".")
            elif "series" in request.vars:
                series_id = request.vars.series
            else:
                series_id = r.id
            if series_id == None:
                # The URL is bad, without a series id we're lost so list all series
                redirect(URL(c="survey",
                             f="series",
                             args=[],
                             vars = {}))
            if "post_vars" in request and len(request.post_vars) > 0:
                id = s3.survey_save_answers_for_series(series_id,
                                                       None, # Insert
                                                       request.post_vars)
                response.confirmation = \
                    s3.crud_strings["survey_complete"].msg_record_created
        return True

    def postp(r, output):
        if r.interactive:
            if "viewing" in request.vars:
                dummy, series_id = request.vars.viewing.split(".")
            elif "series" in request.vars:
                series_id = request.vars.series
            else:
                series_id = r.id
            if output["form"] == None:
                # The user is not authorised to create so switch to read
                redirect(URL(c="survey",
                             f="series",
                             args=[series_id,"read"],
                             vars = {}))
            s3.survey_answerlist_dataTable_post(r)
            form = s3.survey_buildQuestionnaireFromSeries(series_id, None)
            translationList = s3.survey_getAllTranslationsForSeries(series_id)
            urlexport = URL(c=module,
                            f="series_export_formatted",
                            args=[series_id]
                            )
            tranForm = FORM(_action=urlexport)
            tranTable = TABLE()
            tr = TR()
            tr.append(INPUT(_type='radio',
                                _name='translationLanguage',
                                _value="Default",
                                _checked=True,
                               ))
            tr.append(LABEL("Default"))
            tranTable.append(tr)
            for translation in translationList:
                tr = TR()
                tr.append(INPUT(_type='radio',
                                    _name='translationLanguage',
                                    _value=translation["code"],
                                   ))
                tr.append(LABEL(translation["language"]))
                tranTable.append(tr)
            tranForm.append(tranTable)
            exportBtn = INPUT(_type="submit",
                              _id="export_btn",
                              _name="Export_Spreadsheet",
                              _value=T("Download Assessment Template Spreadsheet"),
                              _class="action-btn"
                             )
            tranForm.append(exportBtn)
            urlimport = URL(c=module,
                            f="complete",
                            args=["import.xml"],
                            vars = {"viewing":"%s.%s" % ("survey_series", series_id)}
                            )
            buttons = DIV (A(T("Import completed Assessment Template Spreadsheet"),
                             _href=urlimport,
                             _id="Excel-import",
                             _class="action-btn"
                             ),
                          )
            tranForm.append(buttons)
            output["subtitle"] = tranForm
            output["form"] = form
        return output

    response.s3.prep = prep
    response.s3.postp = postp
    output = s3_rest_controller(prefix,
                                resourcename,
                                method = "create",
                                rheader=s3.survey_series_rheader
                               )
    return output


def complete():
    """ RESTful CRUD controller """
    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]
    s3 = response.s3
    s3.survey_answerlist_dataTable_pre()

    def prep(r):
        if r.method == "create" or r.method == "update":
            if "post_vars" in request and len(request.post_vars) > 0:
                complete_id = r.component_id
                id = s3.survey_save_answers_for_complete(r.id,
                                                         request.post_vars)
                session.confirmation = T("Record created")
                redirect(URL(c="survey",
                             f="complete",
                             args=[r.id,"create"],
                             vars = {}))
        return True

    def postp(r, output):
        if r.method == "create" or r.method == "update":
            form = s3.survey_buildQuestionnaire(r.id)
            output["form"] = form
        elif r.method == "import":
            pass # don't want the import dataTable to be modified
        else:
            s3.survey_answerlist_dataTable_post(r)
        return output

    def import_xls(uploadFile):
        if series_id == None:
            response.error = T("Series details missing")
            return
        openFile = StringIO()
        try:
            import xlrd
            from xlwt.Utils import cell_to_rowcol2
        except ImportError:
            print >> sys.stderr, "ERROR: xlrd & xlwt modules are needed for importing spreadsheets"
            return None
        workbook = xlrd.open_workbook(file_contents=uploadFile)
        sheetR = workbook.sheet_by_name("Assessment")
        sheetM = workbook.sheet_by_name("Metadata")
        header = ''
        body = ''
        for row in xrange(1, sheetM.nrows):
            header += ',"%s"' % sheetM.cell_value(row, 0)
            code = sheetM.cell_value(row, 0)
            qstn = s3.survey_getQuestionFromCode(code, series_id)
            type = qstn["type"]
            count = sheetM.cell_value(row, 1)
            if count != "":
                count = int(count)
                optionList = sheetM.cell_value(row, 2).split("|#|")
            else:
                count = 1
                optionList = None
            if type == "Location" and optionList != None:
                answerList = {}
            elif type == "MultiOption":
                answerList = []
            else:
                answerList = ''
            for col in range(count):
                cell = sheetM.cell_value(row, 3+col)
                (rowR, colR) = cell_to_rowcol2(cell)
                try:
                    response = sheetR.cell_value(rowR, colR)
                except IndexError:
                    response = ""
                """
                    BUG: The option list needs to work in different ways
                    depending on the question type. The question type should
                    be added to the spreadsheet to save extra db calls:

                    * Location save all the data as a hierarchy
                    * MultiOption save all selections
                    * Option save the last selection
                """
                if response != "":
                    if optionList != None:
                        if type == "Location":
                            answerList[optionList[col]]=response
                        elif type == "MultiOption":
                            answerList.append(optionList[col])
                        else:
                            answerList = optionList[col]
                    else:
                        answerList += "%s" % response
            body += ',"%s"' % answerList
        openFile.write(header)
        openFile.write("\n")
        openFile.write(body)
        openFile.seek(0)
        return openFile

    series_id = None
    try:
        if "viewing" in request.vars:
            dummy, series_id = request.vars.viewing.split(".")
            series_name = response.s3.survey_getSeriesName(series_id)
        if series_name != "":
            csv_extra_fields = [dict(label="Series", value=series_name)]
        else:
            csv_extra_fields = []
    except:
        csv_extra_fields = []

    s3mgr.configure("survey_complete", listadd=False, deletable=False)
    response.s3.prep = prep
    response.s3.postp = postp
    response.s3.xls_parser = import_xls
    output = s3_rest_controller(prefix, resourcename,
                                csv_extra_fields=csv_extra_fields)
    return output

def answer():
    """ RESTful CRUD controller """
    # Load Model
    tablename = "%s_%s" % (prefix, resourcename)
    s3mgr.load(tablename)
    table = db[tablename]

    output = s3_rest_controller(prefix, resourcename)
    return output

def analysis():
    """ Bespoke controller """
    # Load Model
#    tablename = "%s_%s" % (prefix, resourcename)
#    s3mgr.load(tablename)
#    table = db[tablename]
    try:
        template_id = request.args[0]
    except:
        pass
    s3mgr.configure("survey_complete",
                    listadd=False,
                    deletable=False)
    output = s3_rest_controller(prefix, "complete")
    return output
