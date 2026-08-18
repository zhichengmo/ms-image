from fastapi import HTTPException
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from mongoengine import Document
from pydantic import BaseModel
from sqlalchemy.orm.strategy_options import _AbstractLoad

from app.lib.oid import OID

ModelType = TypeVar("ModelType", bound=Document)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A Pydantic model class
        * `schema`: A Pydantic model (schema) class
        """
        self.model = model

    def get(self, data_id: Any) -> Optional[ModelType]:
        return self.model.objects().with_id(data_id)

    def get_distinct_values(self, attr: str) -> Optional[ModelType]:
        return self.model.objects().distinct(attr)

    def get_by_query(self, query: dict) -> List[ModelType]:
        return self.model.objects(__raw__=query)

    def get_by_field(self, field_name: str, value: any, many=False) -> Optional[ModelType]:
        if many:
            return self.model.objects(**{field_name: value})
        else:

            return self.model.objects(**{field_name: value}).first()

    def get_multi(
            self, *, skip: int = 0, limit: int = 15
    ) -> List[ModelType]:
        if limit is not None and skip is not None:
            return self.model.objects().skip(skip).limit(limit)
        else:
            return self.model.objects().all()

    def get_by_attribute(self, attr: str) -> List[ModelType]:
        return self.model.objects(__raw__={attr.name: {'$exists': 'true', '$ne': ''}})

    def create(self, obj_in: CreateSchemaType) -> ModelType:
        db_obj = self.model(**obj_in)  # type: ignore
        try:
            db_obj.save()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail="数据库操作失败"
            )
        return db_obj

    def update(
        self,
        *,
        db_id: Union[int, str],
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        db_obj = self.model.objects().with_id(db_id)

        if db_obj is None:
            return None

        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for key in update_data.keys():
            db_obj[key] = update_data[key]

        updated_data = db_obj.save()

        return updated_data

    def remove(self, *, id: int) -> ModelType:
        return self.model.delete({'id': id})

    def add_references(
        self, model: Type[ModelType], value: Union[OID, None]
    ) -> object:
        # Some references would be None
        if not value:
            return None
        data = model.objects().with_id(value)
        if not data:
            raise ValueError(f'{model} with the given OID {value} does not exist.')
        return data

    def add_list_references(
        self, model: Type[ModelType], value: Union[List[OID], None]
    ) -> object:
        if not value:
            return None
        data_list = []
        for ref_id in value:
            data = model.objects().with_id(ref_id)
            if not data:
                raise ValueError(f'{model} with the given OID {value} does not exist.')
            data_list.append(data)
        return data_list
