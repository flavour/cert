# coding: utf8

module = "climate"

ClimateDataPortal = local_import("ClimateDataPortal")
SampleTable = ClimateDataPortal.SampleTable
DSL = local_import("ClimateDataPortal.DSL")

sample_types = SampleTable._SampleTable__types.values()
variable_names = SampleTable._SampleTable__names.keys()

def map_plugin():
    return ClimateDataPortal.MapPlugin(
        env = Storage(globals()),
        year_max = 2100,
        year_min = 1950,
        place_table = climate_place
    )

def index():
    try:
        module_name = deployment_settings.modules[module].name_nice
    except:
        module_name = T("Climate")

    # Include an embedded Overview Map on the index page
    config = gis.get_config()

    if not deployment_settings.get_security_map() or s3_has_role("MapAdmin"):
        catalogue_toolbar = True
    else:
        catalogue_toolbar = False

    search = True
    catalogue_layers = False

    if config.wmsbrowser_url:
        wms_browser = {"name" : config.wmsbrowser_name,
                       "url" : config.wmsbrowser_url}
    else:
        wms_browser = None

    print_service = deployment_settings.get_gis_print_service()
    if print_service:
        print_tool = {"url": print_service}
    else:
        print_tool = {}

    map = gis.show_map(
        lat = 28.5,
        lon = 84.1,
        zoom = 7,
        toolbar = False,
#        catalogue_toolbar=catalogue_toolbar, # T/F, top tabs toolbar
        wms_browser = wms_browser, # dict
        plugins = [
            map_plugin()
        ]
    )

    response.title = module_name
    return dict(
        module_name=module_name,
        map=map
    )

month_names = dict(
    January=1,
    February=2,
    March=3,
    April=4,
    May=5,
    June=6,
    July=7,
    August=8,
    September=9,
    October=10,
    November=11,
    December=12
)

for name, number in month_names.items():
    month_names[name[:3]] = number
for name, number in month_names.items():
    month_names[name.upper()] = number
for name, number in month_names.items():
    month_names[name.lower()] = number

def convert_date(default_month):
    def converter(year_month):
        components = year_month.split("-")
        year = int(components[0])
        assert 1960 <= year, "year must be >= 1960"

        try:
            month_value = components[1]
        except IndexError:
            month = default_month
        else:
            try:
                month = int(month_value)
            except TypeError:
                month = month_names[month_value]

        assert 1 <= month <= 12, "month must be in range 1:12"
        return datetime.date(year, month, 1)
    return converter

def one_of(options):
    def validator(choice):
        assert choice in options, "should be one of %s, not '%s'" % (
            options,
            choice
        )
        return choice
    return validator

aggregation_names = ("Maximum", "Minimum", "Average")

def climate_overlay_data():
    kwargs = dict(request.vars)

    arguments = {}
    errors = []
    for kwarg_name, converter in dict(
        query_expression = str,
    ).iteritems():
        try:
            value = kwargs.pop(kwarg_name)
        except KeyError:
            errors.append("%s missing" % kwarg_name)
        else:
            try:
                arguments[kwarg_name] = converter(value)
            except TypeError:
                errors.append("%s is wrong type" % kwarg_name)
            except AssertionError, assertion_error:
                errors.append("%s: %s" % (kwarg_name, assertion_error))
    if kwargs:
        errors.append("Unexpected arguments: %s" % kwargs.keys())

    if errors:
        raise HTTP(400, "<br />".join(errors))
    else:
        try:
            data_path = map_plugin().get_overlay_data(**arguments)
        except SyntaxError, exception:
            import gluon.contrib.simplejson as JSON
            raise HTTP(400, JSON.dumps({
                "error": "SyntaxError",
                "lineno": exception.lineno,
                "offset": exception.offset
            }))
        except DSL.MeaninglessUnitsException, exception:
            import gluon.contrib.simplejson as JSON
            raise HTTP(400, JSON.dumps({
                "error": "MeaninglessUnits",
                "analysis": str(exception)
            }))
        else:
            return response.stream(
                open(data_path,"rb"),
                chunk_size=4096
            )

def list_of(converter):
    def convert_list(choices):
        return map(converter, choices)
    return convert_list

def climate_chart():
    import gluon.contenttype
    data_image_file_path = _climate_chart(gluon.contenttype.contenttype(".png"))
    return response.stream(
        open(data_image_file_path,"rb"),
        chunk_size=4096
    )

def _climate_chart(content_type):
    kwargs = dict(request.vars)
    import gluon.contrib.simplejson as JSON
    specs = JSON.loads(kwargs.pop("spec"))

    checked_specs = []
    for spec in specs:
        arguments = {}
        errors = []
        for name, converter in dict(
            query_expression = str,
            place_ids = list_of(int)
        ).iteritems():
            try:
                value = spec.pop(name)
            except KeyError:
                errors.append("%s missing" % name)
            else:
                try:
                    arguments[name] = converter(value)
                except TypeError:
                    errors.append("%s is wrong type" % name)
                except AssertionError, assertion_error:
                    errors.append("%s: %s" % (name, assertion_error))
        if spec:
            errors.append("Unexpected arguments: %s" % spec.keys())
        checked_specs.append(arguments)

    if errors:
        raise HTTP(400, "<br />".join(errors))
    else:
        response.headers["Content-Type"] = content_type
        data_image_file_path = map_plugin().render_plots(
            specs = checked_specs,
            width = int(kwargs.pop("width")),
            height = int(kwargs.pop("height"))
        )
        return data_image_file_path

def climate_chart_download():
    data_image_file_path = _climate_chart("application/force-download")
    import os
    response.headers["Content-disposition"] = (
        "attachment; filename=" +
        os.path.basename(data_image_file_path)
    )
    return response.stream(
        open(data_image_file_path,"rb"),
        chunk_size=4096
    )

def chart_popup():
    return {}

def buy_data():
    return {}

def stations():
    "return all station data in JSON format"
    stations_strings = []
    append = stations_strings.append
    extend = stations_strings.extend

    for place_row in db(
        (db.climate_place.id == db.climate_place_elevation.id) &
        (db.climate_place.id == db.climate_place_station_id.id) &
        (db.climate_place.id == db.climate_place_station_name.id)
    ).select(
        db.climate_place.id,
        db.climate_place.longitude,
        db.climate_place.latitude,
        db.climate_place_elevation.elevation_metres,
        db.climate_place_station_id.station_id,
        db.climate_place_station_name.name
    ):
        append(
            "".join((
                "(", str(place_row.climate_place.id), ",{",
                    '"longitude":', str(place_row.climate_place.longitude),
                    ',"latitude":', str(place_row.climate_place.latitude),
                "}"
            ))
        )
    return "[%s]" % ",".join(stations_strings)

def places():
    "return all place data in JSON format"
    places_strings = []
    append = places_strings.append
    extend = places_strings.extend

    for place_row in db().select(
        db.climate_place.id,
        db.climate_place.longitude,
        db.climate_place.latitude,
        db.climate_place_elevation.elevation_metres,
        db.climate_place_station_id.station_id,
        db.climate_place_station_name.name,
        db.climate_place_region.region_id,
        left = (
            db.climate_place_region.on(
                db.climate_place.id == db.climate_place_region.id
            ),
            db.climate_place_elevation.on(
                (db.climate_place.id == db.climate_place_elevation.id)
            ),
            db.climate_place_station_id.on(
                (db.climate_place.id == db.climate_place_station_id.id)
            ),
            db.climate_place_station_name.on(
                (db.climate_place.id == db.climate_place_station_name.id)
            )
        )
    ):
        append(
            "".join((
                "[", str(place_row.climate_place.id), ",{",
                    '"longitude":', str(place_row.climate_place.longitude),
                    ',"latitude":', str(place_row.climate_place.latitude),
                    ',"elevation":', str(place_row.climate_place_elevation.elevation_metres or "null"),
                    ',"station_id":', str(place_row.climate_place_station_id.station_id or "null"),
                    ',"name":"', (
                        place_row.climate_place_station_name.name or "%sN %sE" % (
                            place_row.climate_place.latitude,
                            place_row.climate_place.longitude
                        )
                    ).replace('"', '\\"'),'"'
                    ',"region_id":', str(place_row.climate_place_region.region_id or "null"),
                "}]"
            ))
        )
    return "[%s]" % ",".join(places_strings)

