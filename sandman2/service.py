"""Automatically generated REST API services from SQLAlchemy
ORM models or a database introspection."""

import sys

# Third-party imports
from flask import request, make_response
import flask
from flask.views import MethodView
from sqlalchemy import asc, desc
from sqlalchemy.sql import text
from datetime import datetime

# Application imports
from sandman2.exception import NotFoundException, BadRequestException
from sandman2.model import db
from sandman2.decorators import etag, validate_fields


def add_link_headers(response, links):
    """Return *response* with the proper link headers set, based on the contents
    of *links*.

    :param response: :class:`flask.Response` response object for links to be
                     added
    :param dict links: Dictionary of links to be added
    :rtype :class:`flask.Response` :
    """
    link_string = '<{}>; rel=self'.format(links['self'])
    for link in links.values():
        link_string += ', <{}>; rel=related'.format(link)
    response.headers['Link'] = link_string
    return response


def jsonify(resource):
    """Return a Flask ``Response`` object containing a
    JSON representation of *resource*.

    :param resource: The resource to act as the basis of the response
    """

    response = flask.jsonify(resource.to_dict())
    response = add_link_headers(response, resource.links())
    return response


def is_valid_method(model, resource=None):
    """Return the error message to be sent to the client if the current
    request passes fails any user-defined validation."""
    validation_function_name = 'is_valid_{}'.format(
        request.method.lower())
    if hasattr(model, validation_function_name):
        return getattr(model, validation_function_name)(request, resource)

class Service(MethodView):

    """The *Service* class is a generic extension of Flask's *MethodView*,
    providing default RESTful functionality for a given ORM resource.

    Each service has an associated *__model__* attribute which represents the
    ORM resource it exposes. Services are JSON-only. HTML-based representation
    is available through the admin interface.
    """

    #: The sandman2.model.Model-derived class to expose
    __model__ = None

    #: The string used to describe the elements when a collection is
    #: returned.
    __json_collection_name__ = 'resources'

    def delete(self, resource_id):
        """Return an HTTP response object resulting from a HTTP DELETE call.

        :param resource_id: The value of the resource's primary key
        """
        resource = self._resource(resource_id)
        error_message = is_valid_method(self.__model__, resource)
        if error_message:
            raise BadRequestException(error_message)
        db.session().delete(resource)
        db.session().commit()
        return self._no_content_response()

    @etag
    def get(self, resource_id=None):
        """Return an HTTP response object resulting from an HTTP GET call.

        If *resource_id* is provided, return just the single resource.
        Otherwise, return the full collection.

        :param resource_id: The value of the resource's primary key
        """
        if request.path.endswith('meta'):
            return self._meta()

        if resource_id is None:
            error_message = is_valid_method(self.__model__)
            if error_message:
                raise BadRequestException(error_message)

            if 'export' in request.args:
                return self._export(self._all_resources())

            if 'collection' in request.args:
                if 'split' in request.args:
                    # column seen as a date and split into three more fields: year, month, day
                    results = self._all_resources()
                    splits = request.args['split'].split(',')
                    scolumn = splits[0]
                    sformat = splits[1]
                    tr_results = []
                    for result in results:
                        sdate = str(result[scolumn])
                        date = datetime.strptime(sdate, sformat)
                        result[scolumn+"_year"] = date.year
                        result[scolumn+"_month"] = date.month
                        result[scolumn+"_day"] = date.day
                        tr_results.append(result)
                    return flask.jsonify(tr_results)
                else:
                    return flask.jsonify(self._all_resources())

            return flask.jsonify({
                self.__json_collection_name__: self._all_resources()
                })
        else:
            resource = self._resource(resource_id)
            error_message = is_valid_method(self.__model__, resource)
            if error_message:
                raise BadRequestException(error_message)
            return jsonify(resource)

    def patch(self, resource_id):
        """Return an HTTP response object resulting from an HTTP PATCH call.

        :returns: ``HTTP 200`` if the resource already exists
        :returns: ``HTTP 400`` if the request is malformed
        :returns: ``HTTP 404`` if the resource is not found
        :param resource_id: The value of the resource's primary key
        """
        resource = self._resource(resource_id)
        error_message = is_valid_method(self.__model__, resource)
        if error_message:
            raise BadRequestException(error_message)
        if not request.json:
            raise BadRequestException('No JSON data received')
        resource.update(request.json)
        db.session().merge(resource)
        db.session().commit()
        return jsonify(resource)

    @validate_fields
    def post(self):
        """Return the JSON representation of a new resource created through
        an HTTP POST call.

        :returns: ``HTTP 201`` if a resource is properly created
        :returns: ``HTTP 204`` if the resource already exists
        :returns: ``HTTP 400`` if the request is malformed or missing data
        """
        resource = self.__model__.query.filter_by(**request.json).first()
        if resource:
            error_message = is_valid_method(self.__model__, resource)
            if error_message:
                raise BadRequestException(error_message)
            return self._no_content_response()

        resource = self.__model__(**request.json)  # pylint: disable=not-callable
        error_message = is_valid_method(self.__model__, resource)
        if error_message:
            raise BadRequestException(error_message)
        db.session().add(resource)
        db.session().commit()
        return self._created_response(resource)

    def put(self, resource_id):
        """Return the JSON representation of a new resource created or updated
        through an HTTP PUT call.

        If resource_id is not provided, it is assumed the primary key field is
        included and a totally new resource is created. Otherwise, the existing
        resource referred to by *resource_id* is updated with the provided JSON
        data. This method is idempotent.

        :returns: ``HTTP 201`` if a new resource is created
        :returns: ``HTTP 200`` if a resource is updated
        :returns: ``HTTP 400`` if the request is malformed or missing data
        """
        resource = self.__model__.query.get(resource_id)
        if resource:
            error_message = is_valid_method(self.__model__, resource)
            if error_message:
                raise BadRequestException(error_message)
            resource.update(request.json)
            db.session().merge(resource)
            db.session().commit()
            return jsonify(resource)

        resource = self.__model__(**request.json)  # pylint: disable=not-callable
        error_message = is_valid_method(self.__model__, resource)
        if error_message:
            raise BadRequestException(error_message)
        db.session().add(resource)
        db.session().commit()
        return self._created_response(resource)

    def _meta(self):
        """Return a description of this resource as reported by the
        database."""
        return flask.jsonify(self.__model__.description())

    def _resource(self, resource_id):
        """Return the ``sandman2.model.Model`` instance with the given
        *resource_id*.

        :rtype: :class:`sandman2.model.Model`
        """
        resource = self.__model__.query.get(resource_id)
        if not resource:
            raise NotFoundException()
        return resource

    def prepareDate(self, key, value, backend, filters):
        """Set Date Filter
        """
        key = f"`{key}`"
        values = value.split(",")
        if len(values) > 2:
            if backend == 'sqlite':
                ftext = f"date({key}) between date('{values[1]}') and date('{values[2]}')"
                filters.append(text(ftext))
            elif backend == 'mysql':
                ftext = f"date({key}) between date('{values[1]}') and date('{values[2]}')"
                filters.append(text(ftext))
            else:
                raise BadRequestException('Invalid backend for Date processing')
        else:
            if backend == 'sqlite':
                ftext = f"date({key}) = date('{values[1]}')"
                filters.append(text(ftext))
            elif backend == 'mysql':
                ftext = f"date({key}) = date('{values[1]}')"
                filters.append(text(ftext))
            else:
                raise BadRequestException('Invalid backend for Date processing')

    def prepareYear(self, key, value, backend, filters):
        """Set year Filter
        """
        key = f"`{key}`"
        values = value.split(",")
        if len(values) > 2:
            if backend == 'sqlite':
                ftext = f"cast(strftime('%Y',{key}) AS INTEGER)  between {values[1]} and {values[2]}"
                filters.append(text(ftext))
            elif backend == 'mysql':
                ftext = f"year(date({key})) between {values[1]} and {values[2]}"
                filters.append(text(ftext))
            else:
                raise BadRequestException('Invalid backend for Year processing')
        else:
            if backend == 'sqlite':
                ftext = f"cast(strftime('%Y',{key}) AS INTEGER) = {values[1]}"
                filters.append(text(ftext))
            elif backend == 'mysql':
                ftext = f"year(date({key})) = {values[1]}"
                filters.append(text(ftext))
            else:
                raise BadRequestException('Invalid backend for Year processing')

    def _all_resources(self):
        """Return the complete collection of resources as a list of
        dictionaries.

        :rtype: :class:`sandman2.model.Model`
        """
        db.engine.echo = True
        backend = ""
        if 'sqlite' in db.engine.name:
            backend = 'sqlite'
        elif 'mysql' in db.engine.name:
            backend = 'mysql'
        queryset = self.__model__.query
        args = {k: v for (k, v) in request.args.items() 
                if (k not in ('page', 'export', 'collection','split')
                    and not k.isnumeric())}
        limit = None
        if args:
            filters = []
            order = []
            for key, value in args.items():
                #flask.current_app.logger.debug(value)
                print(f"{key}={value}", file=sys.stdout, flush=True)
                if value.startswith('%'):
                    filters.append(
                        getattr(self.__model__, key).like(str(value), 
                                                          escape='/'))
                elif key == 'sort':
                    direction = desc if value.startswith('-') else asc
                    order.append(direction(getattr(self.__model__, 
                                                   value.lstrip('-'))))
                elif key == 'limit':
                    limit = int(value)
                elif hasattr(self.__model__, key):
                    if value.startswith("DATE"):
                        self.prepareDate(key, value, backend, filters)
                    elif value.startswith("YEAR"):
                        self.prepareYear(key, value, backend, filters)
                    elif "|" in value:
                        values = value.split("|")
                        filters.append(getattr(self.__model__, key).in_(values))
                    else:
                        filters.append(getattr(self.__model__, key) == value)
                else:
                    raise BadRequestException('Invalid field [{}]'.format(key))
            queryset = queryset.filter(*filters).order_by(*order)
        if 'page' in request.args:
            resources = queryset.paginate(page=int(request.args['page']),
                                          per_page=limit).items
        else:
            queryset = queryset.limit(limit)
            resources = queryset.all()
        db.engine.echo = False
        return [r.to_dict() for r in resources]

    def _export(self, collection):
        """Return a CSV of the resources in *collection*.

        :param list collection: A list of resources represented by dicts
        """
        fieldnames = collection[0].keys()
        faux_csv = ','.join(fieldnames) + '\r\n'
        for resource in collection:
            faux_csv += ','.join((str(x) for x in resource.values())) + '\r\n'
        response = make_response(faux_csv)
        response.mimetype = 'text/csv'
        return response


    @staticmethod
    def _no_content_response():
        """Return an HTTP 204 "No Content" response.

        :returns: HTTP Response
        """
        response = make_response()
        response.status_code = 204
        return response

    @staticmethod
    def _created_response(resource):
        """Return an HTTP 201 "Created" response.

        :returns: HTTP Response
        """
        response = jsonify(resource)
        response.status_code = 201
        return response
