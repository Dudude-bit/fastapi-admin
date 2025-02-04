import gc
import inspect
from typing import List, Optional, Type

from fastapi import Depends, HTTPException
from fastapi.params import Path
from mongoengine import Document
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND
from fastapi_admin.exceptions import InvalidResource
from fastapi_admin.resources import Dropdown, Link, Model, Resource
import mongoengine


def get_model(resource: Optional[str] = Path(...)): # TODO remake with getting all models on init
    if not resource:
        return
    models = {
        obj._get_collection_name(): obj for obj in gc.get_objects() if inspect.isclass(obj)
                                                                   and issubclass(obj, Document)
                                                                   and obj is not Document
                                                                   and obj._get_collection_name() is not None
    }
    return models[resource]


async def get_model_resource(request: Request, model=Depends(get_model)):
    model_resource = request.app.get_model_resource(model)  # type:Model
    if not model_resource:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND)
    actions = await model_resource.get_actions(request)
    bulk_actions = await model_resource.get_bulk_actions(request)
    toolbar_actions = await model_resource.get_toolbar_actions(request)
    setattr(model_resource, "toolbar_actions", toolbar_actions)
    setattr(model_resource, "actions", actions)
    setattr(model_resource, "bulk_actions", bulk_actions)
    return model_resource


def _get_resources(resources: List[Type[Resource]]):
    ret = []
    for resource in resources:
        item = {
            "icon": resource.icon,
            "label": resource.label,
        }
        if issubclass(resource, Link):
            item["type"] = "link"
            item["url"] = resource.url
            item["target"] = resource.target
        elif issubclass(resource, Model):
            item["type"] = "model"
            item["model"] = resource.model.__name__.lower()
        elif issubclass(resource, Dropdown):
            item["type"] = "dropdown"
            item["resources"] = _get_resources(resource.resources)
        else:
            raise InvalidResource("Should be subclass of Resource")
        ret.append(item)
    return ret


def get_resources(request: Request) -> List[dict]:
    resources = request.app.resources
    return _get_resources(resources)


def get_redis(request: Request):
    return request.app.redis


def get_current_admin(request: Request):
    admin = request.state.admin
    if not admin:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)
    return admin
