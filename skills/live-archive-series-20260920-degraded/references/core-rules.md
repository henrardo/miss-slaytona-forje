# Core rules

## additional-triggers

- A project still uses BaseSettings, Config, validator, root_validator, allow_reuse, __fields__, ModelField, field_info.extra, SHAPE_LIST, regex, parse_obj, dict, json, or other Pydantic v1 interfaces
- Dependency metadata permits or requires Pydantic 2 but runtime behavior or tests remain written for Pydantic 1

## execution-discipline

Work in small semantic units: inspect the complete original body, change one related construct, compile or import it, run the narrowest relevant test, inspect the diff, and only then continue. Use exact paths copied from `pwd`; repeated mistyped paths are a signal to stop and verify location. Do not narrate success or end the turn while tests remain red.