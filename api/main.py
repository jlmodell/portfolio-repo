import datetime
from http.client import HTTPException
import os
from pydoc import doc
from typing import Dict, Optional, Union
import uuid
from fastapi import Body, Depends, FastAPI, APIRouter, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import redis
from pydantic import BaseModel, Field, BaseSettings, RedisDsn
from beanie import init_beanie, Document
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

USERS_COLLECTION = os.environ.get("USERS", None)
assert USERS_COLLECTION is not None, "USERS is not set"


class Todo(BaseModel):
    description: Optional[Union[str, None]] = Field(
        None, description="todo description...")
    updatedAt: datetime.datetime = Field(
        default_factory=datetime.datetime.now, description="timestamp for last update")
    completed: Union[bool, None] = Field(
        default=False, description="whether the todo is completed or not...")
    deleted: Union[bool, None] = Field(
        default=False, description="whether the todo is deleted or not...")


class User(Document):
    username: str = Field(...)
    createdAt: datetime.datetime = Field(default_factory=datetime.datetime.now)
    active: bool = Field(...)
    todos: Dict[str, Todo] = Field(default={})

    class Collection:
        name = USERS_COLLECTION


class Settings(BaseSettings):
    mongodb_host: str = os.environ.get("MONGODB_HOST", None)
    mongodb_user: str = os.environ.get("MONGODB_USER", None)
    mongodb_pass: str = os.environ.get("MONGODB_PASS", None)
    mongodb_db: str = os.environ.get("MONGODB_DB", None)

    redis_host: str = os.environ.get("REDIS_HOST", None)
    redis_port: int = os.environ.get("REDIS_PORT", None)
    redis_pass: str = os.environ.get("REDIS_PASS", None)

    @property
    def mongo_dsn(self):
        assert self.mongodb_host is not None, "MONGODB_HOST is not set"
        assert self.mongodb_user is not None, "MONGODB_USER is not set"
        assert self.mongodb_pass is not None, "MONGODB_PASS is not set"

        return "mongodb://{0}:{1}@{2}:27017/?authSource=admin".format(self.mongodb_user, self.mongodb_pass, self.mongodb_host)

    @property
    def redis_dsn(self) -> RedisDsn:
        assert self.redis_host is not None, "REDIS_HOST is not set"
        assert self.redis_port is not None, "REDIS_PORT is not set"
        assert self.redis_pass is not None, "REDIS_PASS is not set"

        return redis.Redis(hostname=self.redis_host, port=self.redis_port, password=self.redis_pass)


router = APIRouter()


def paginate(page: int = 1):
    if page <= 1:
        return 0
    else:
        return (page - 1) * 10


@router.get("/users")
async def get_user(username: str = None):
    doc = await User.find_one({"username": username})

    if not doc:
        raise HTTPException(
            status_code=404, detail="{0} not found".format(username))

    return doc


@router.get("/users/{page}")
async def get_users(skip: int = Depends(paginate)):
    docs = await User.find_all(skip=skip, limit=10).to_list()
    if not docs:
        return JSONResponse(dict(status_code=404, message=f"users not found"))

    return docs


@router.post("/users/todos/add")
async def add_todo_to_users_list(todo: Todo = Body(), user: Union[str, None] = Header(default=None)):
    id = uuid.uuid4()

    doc = await User.find_one({"username": user})
    if not doc:
        return JSONResponse(dict(status_code=404, message=f"{user} not found"))

    doc.todos[str(id)] = {
        "description": todo.description,
        "completed": todo.completed,
        "updatedAt": todo.updatedAt,
        "deleted": todo.deleted,
    }

    await doc.save()

    return JSONResponse(content={"message": f"successfully inserted todo with id {id}"}, status_code=201)


@router.put("/users/todos/update/{id}")
async def update_todo_in_users_list(id: str = Field(...), todo: Todo = Body(), user: Union[str, None] = Header(default=None)):
    doc = await User.find_one({"username": user})

    if not doc:
        return JSONResponse(dict(status_code=404, message=f"{user} not found"))

    doc.todos[id] = {
        "description": todo.description if todo.description != None else doc.todos[id].description,
        "completed": todo.completed if todo.completed != None else doc.todos[id].completed,
        "deleted": todo.deleted if todo.deleted != None else doc.todos[id].deleted,
        "updatedAt": datetime.datetime.now(),
    }

    await doc.save()

    return JSONResponse(content=dict(message=f"successfully updated todo with id {id}", status_code=200))


@router.delete("/users/todos/delete/{id}")
async def delete_todo_in_users_list(id: str = Field(...), user: Union[str, None] = Header(default=None)):
    doc = await User.find_one({"username": user})

    if not doc:
        return JSONResponse(dict(status_code=404, message=f"{user} not found"))

    doc.todos[id].deleted = False if doc.todos[id].deleted else True

    await doc.save()

    return JSONResponse(content=dict(message=f"successfully deleted todo with id {id}", status_code=204))


app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def app_init(document_models=[User]):
    settings = Settings()

    client = AsyncIOMotorClient(settings.mongo_dsn)
    db = client[settings.mongodb_db]

    await init_beanie(database=db, document_models=document_models)

    app.include_router(router, prefix="/api/v1", tags=["user", "users"])
