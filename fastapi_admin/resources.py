from typing import Any, Dict, List, Optional, Tuple, Type, Union

from mongoengine import BooleanField, DateField, DateTimeField, IntField, StringField, DictField, Document, QuerySet, \
    ObjectIdField, EmbeddedDocumentField, EmbeddedDocumentListField
from pydantic import BaseModel, validator
from starlette.datastructures import FormData
from starlette.requests import Request

from fastapi_admin.enums import Method
from fastapi_admin.exceptions import NoSuchFieldFound
from fastapi_admin.i18n import _
from fastapi_admin.widgets import Widget, displays, inputs
from fastapi_admin.widgets.filters import Filter, Search


class Resource:
    """
    Base Resource
    """

    label: str
    icon: str = ""


class Link(Resource):
    url: str
    target: str = "_self"


class Field:
    name: str
    label: str
    display: displays.Display
    input: inputs.Input

    def __init__(
        self,
        name: str,
        label: Optional[str] = None,
        display: Optional[displays.Display] = None,
        input_: Optional[Widget] = None,
    ):
        self.name = name
        self.label = label or name.title()
        if not display:
            display = displays.Display()
        display.context.update(label=self.label)
        self.display = display
        if not input_:
            input_ = inputs.Input()
        input_.context.update(label=self.label, name=name)
        self.input = input_


class ComputeField(Field):
    async def get_value(self, request: Request, obj: Document):
        return getattr(obj, self.name)


class Action(BaseModel):
    icon: str
    label: str
    name: str
    method: Method = Method.POST
    ajax: bool = True

    @validator("ajax")
    def ajax_validate(cls, v: bool, values: dict, **kwargs):
        if not v and values["method"] != Method.GET:
            raise ValueError("ajax is False only available when method is Method.GET")


class ToolbarAction(Action):
    class_: Optional[str]


class Model(Resource):
    model: Type[Document]
    fields: List[Union[str, Field, ComputeField]] = []
    page_size: int = 10
    page_pre_title: Optional[str] = None
    page_title: Optional[str] = None
    filters: List[Union[str, Filter]] = []

    async def get_toolbar_actions(self, request: Request) -> List[ToolbarAction]:
        return [
            ToolbarAction(
                label=_("create"),
                icon="fas fa-plus",
                name="create",
                method=Method.GET,
                ajax=False,
                class_="btn-dark",
            )
        ]

    async def row_attributes(self, request: Request, obj: dict) -> dict:
        return {}

    async def column_attributes(self, request: Request, field: Field) -> dict:
        return {}

    async def cell_attributes(self, request: Request, obj: dict, field: Field) -> dict:
        return {}

    async def get_actions(self, request: Request) -> List[Action]:
        return [
            Action(
                label=_("update"), icon="ti ti-edit", name="update", method=Method.GET, ajax=False
            ),
            Action(label=_("delete"), icon="ti ti-trash", name="delete", method=Method.DELETE),
        ]

    async def get_bulk_actions(self, request: Request) -> List[Action]:
        return [
            Action(
                label=_("delete_selected"),
                icon="ti ti-trash",
                name="delete",
                method=Method.DELETE,
            ),
        ]

    @classmethod
    async def get_inputs(cls, request: Request, obj: Optional[Document] = None):
        ret = []
        for field in cls.get_fields(is_display=False):
            input_ = field.input
            if isinstance(input_, inputs.DisplayOnly):
                continue
            if isinstance(input_, inputs.File):
                cls.enctype = "multipart/form-data"
            name = input_.context.get("name")
            print(name, flush=True)
            print(obj, flush=True)
            ret.append(await input_.render(request, getattr(obj, name, None)))
        return ret

    @classmethod
    async def resolve_query_params(cls, request: Request, values: dict, qs: QuerySet):
        ret = {}
        for f in cls.filters:
            if isinstance(f, str):
                f = Search(name=f, label=f.title())
            name = f.context.get("name")
            v = values.get(name)
            if v is not None and v != "":
                ret[name] = await f.parse_value(request, v)
                qs = await f.get_queryset(request, v, qs)
        return ret, qs

    @classmethod
    async def resolve_data(cls, request: Request, data: FormData):
        ret = {}
        m2m_ret = {}
        for field in cls.get_fields(is_display=False):
            input_ = field.input
            if input_.context.get("disabled") or isinstance(input_, inputs.DisplayOnly):
                continue
            name = input_.context.get("name")
            if isinstance(input_, inputs.ManyToMany):
                v = data.getlist(name)
                value = await input_.parse_value(request, v)
                m2m_ret[name] = await input_.model.objects.filter(pk__in=value)
            else:
                v = data.get(name)
                value = await input_.parse_value(request, v)
                if value is None:
                    continue
                ret[name] = value
        return ret, m2m_ret

    @classmethod
    async def get_filters(cls, request: Request, values: Optional[dict] = None):
        if not values:
            values = {}
        ret = []
        for f in cls.filters:
            if isinstance(f, str):
                f = Search(name=f, label=f.title())
            name = f.context.get("name")
            value = values.get(name)
            ret.append(await f.render(request, value))
        return ret

    @classmethod
    def _get_fields_attr(cls, attr: str, display: bool = True):
        ret = []
        for field in cls.get_fields():
            if display and isinstance(field.display, displays.InputOnly):
                continue
            ret.append(getattr(field, attr))
        return ret or cls.model._meta.db_fields

    @classmethod
    def get_fields_name(cls, display: bool = True):
        return cls._get_fields_attr("name", display)

    @classmethod
    def _get_display_input_field(cls, field_name: str) -> Field:
        fields_map = cls.model._fields
        field = fields_map.get(field_name)
        if not field:
            raise NoSuchFieldFound(f"Can't found field '{field_name}' in model {cls.model}")
        label = field_name
        null = field.null
        placeholder = getattr(field, 'description', "")
        display, input_ = displays.Display(), inputs.Input(
            placeholder=placeholder, null=null, default=field.default
        )
        if field.primary_key:
            display, input_ = displays.Display(), inputs.DisplayOnly()
        elif isinstance(field, BooleanField):
            display, input_ = displays.Boolean(), inputs.Switch(null=null, default=field.default)
        elif isinstance(field, DateTimeField):
            display, input_ = displays.DatetimeDisplay(), inputs.DateTime(null=null, default=field.default)
        elif isinstance(field, DateField):
            display, input_ = displays.DateDisplay(), inputs.Date(null=null, default=field.default)
        elif isinstance(field, DictField):
            display, input_ = displays.Json(), inputs.Json(null=null)
        elif isinstance(field, StringField):
            display, input_ = displays.Display(), inputs.TextArea(
                placeholder=placeholder, null=null, default=field.default
            )
        elif isinstance(field, IntField):
            display, input_ = displays.Display(), inputs.Number(
                placeholder=placeholder, null=null, default=field.default
            )
        elif isinstance(field, ObjectIdField):
            display, input_ = displays.Display(), inputs.ObjectIdText(
                placeholder=placeholder, null=null, default=field.default
            )
        elif isinstance(field, EmbeddedDocumentField):
            display, input_ = displays.Display(), inputs.EmbeddedDocumentInput(
                placeholder=placeholder, null=null, default=field.default
            )
        elif isinstance(field, EmbeddedDocumentListField):
            display, input_ = displays.Display(), inputs.EmbeddedDocumentListInput(
                placeholder=placeholder, null=null, default=field.default
            )
        return Field(name=field_name, label=label.title(), display=display, input_=input_)

    @classmethod
    def get_fields(cls, is_display: bool = True):
        ret = []
        pk_column = cls.model._meta['id_field']
        for field in cls.fields or cls.model._fields:
            if isinstance(field, str):
                if field == pk_column:
                    continue
                field = cls._get_display_input_field(field)
            if isinstance(field, ComputeField) and not is_display:
                continue
            elif isinstance(field, Field):
                if field.name == pk_column:
                    continue
                if (is_display and isinstance(field.display, displays.InputOnly)) or (
                    not is_display and isinstance(field.input, inputs.DisplayOnly)
                ):
                    continue
            ret.append(field)
        ret.insert(0, cls._get_display_input_field(pk_column))
        return ret

    @classmethod
    def get_fields_label(cls, display: bool = True):
        return cls._get_fields_attr("label", display)

    @classmethod
    def get_m2m_field(cls):
        ret = []
        for field in cls.fields or cls.model._meta.fields:
            if isinstance(field, Field):
                field = field.name
            if field in cls.model._meta.m2m_fields:
                ret.append(field)
        return ret


class Dropdown(Resource):
    resources: List[Type[Resource]]


async def render_values(
    request: Request,
    model: "Model",
    fields: List["Field"],
    values: List[Dict[str, Any]],
    display: bool = True,
) -> Tuple[List[List[Any]], List[dict], List[dict], List[List[dict]]]:
    """
    render values with template render
    :params model:
    :params request:
    :params fields:
    :params values:
    :params display:
    :params request:
    :params model:
    :return:
    """
    ret = []
    cell_attributes: List[List[dict]] = []
    row_attributes: List[dict] = []
    column_attributes: List[dict] = []
    for field in fields:
        column_attributes.append(await model.column_attributes(request, field))
    for value in values:
        row_attributes.append(await model.row_attributes(request, value))
        item = []
        cell_item = []
        for field in fields:
            if isinstance(field, ComputeField):
                v = await field.get_value(request, value)
            else:
                v = getattr(value, field.name)
            cell_item.append(await model.cell_attributes(request, value, field))
            if display:
                item.append(await field.display.render(request, v))
            else:
                item.append(await field.input.render(request, v))
        ret.append(item)
        cell_attributes.append(cell_item)
    return ret, row_attributes, column_attributes, cell_attributes
