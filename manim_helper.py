import json
import pprint
import warnings
from typing import Any
from dataclasses import dataclass

from manim import *


class MObjectManager:

    class InvalidObjectException(Exception):
        pass

    @staticmethod
    def _mobject_shift(_: 'MObjectManager', o: Mobject, v: str) -> None:
        o.shift(eval(v))

    @staticmethod
    def _mobject_color(_: 'MObjectManager', o: Mobject, v: str) -> None:
        o.set_color(v)

    @staticmethod
    def _mobject_scale(_: 'MObjectManager', o: Mobject, v: float) -> None:
        o.scale(v)

    @staticmethod
    def _mobject_move_to(m: 'MObjectManager', o: Mobject, d: str) -> None:
        o.move_to(m.get_object(d))

    supported_attributes = {}

    def __init__(self) -> None:
        self._objects: list[str] = []

    def get_object(self, name: str) -> Any:
        if name not in self._objects:
            raise MObjectManager.InvalidObjectException(
                f'Cannot find object "{name}"'
            )
        return getattr(self, name)

    def add_object(self, name: str, value: Any) -> None:
        if name in self._objects:
            raise MObjectManager.InvalidObjectException(
                f'Object `{name}` already exists'
            )
        
        setattr(self, name, value)
        self._objects.append(name)

    def update_attributes(self) -> None:
        for attr in self._objects:
            value = getattr(self, attr)
            if isinstance(value, str):
                setattr(self, attr, Text(value))

            if isinstance(value, dict):
                if 'type' not in value:
                    value['type'] = 'text'
                if 'value' not in value:
                    raise MObjectManager.InvalidObjectException(
                        f'Object `{attr}` should has an value'
                    )

                try:
                    setattr(
                        self, attr, 
                        eval(f'{value["type"][0].upper()}{value["type"][1:]}')(value['value'])
                    )
                except Exception as e:
                    raise MObjectManager.InvalidObjectException(
                        'Failed to create object'
                    ) from e

                for k, v in value.items():
                    if k in ('type', 'value'):
                        continue
                    elif k not in MObjectManager.supported_attributes:
                        raise MObjectManager.InvalidObjectException(
                            f'Unsupported attribute: {k}'
                        )
                    else:
                        MObjectManager.supported_attributes[k](self, getattr(self, attr), v)

MObjectManager.supported_attributes = { 
    '_'.join(key.split('_')[2:]): getattr(MObjectManager, key) for key in dir(MObjectManager) if key.startswith('_mobject_')   
}


class TextLoader:
    '''
    A simple loader to load text content from a json file

    Syntax:    "[{id}.]{names}[-{qualification}]*
    '''
    class LoadException(Exception):
        pass

    def __init__(self, text_file: str) -> None:
        self._src_file = text_file


    def load(self) -> dict[str, str]:
        raw_content: dict[str, str]
        try:
            with open(self._src_file, 'r', encoding='utf-8') as f:
                raw_content = json.loads(f.read())

        except (OSError, json.JSONDecodeError) as e:
            raise TextLoader.LoadException(
                f'Error while deserializing json object: {e}'
            )
        except Exception as fatal:
            raise TextLoader.LoadException(fatal)

        return raw_content
    
    def apply_to(self, o: object, content: dict[str, Any]) -> None:
        if o is not None:
            for k, v in content.items():
                index_num = ''
                remains = ''
                formatted_name = ''
                if len(index := k.split('.')) not in (1, 2):
                    raise TextLoader.LoadException(
                        f'Invalid syntax: `.` should only be used to mark index'
                    )
                elif len(index) == 1:
                    remains = index[0]
                elif len(index) == 2:
                    index_num, remains = index
                    try:
                        int(index_num)
                    except ValueError as e:
                        raise TextLoader.LoadException(
                            f'Invalid index format: {e}'
                        )

                remains = remains.replace('-', '_')
                formatted_name = remains if not index_num else f'{remains}_{index_num}'
                setattr(o, formatted_name, v)


    def apply(self, content: dict[str, Any]) -> MObjectManager:
        manager = MObjectManager()

        for k, v in content.items():
            index_num = ''
            remains = ''
            formatted_name = ''
            if len(index := k.split('.')) not in (1, 2):
                raise TextLoader.LoadException(
                    f'Invalid syntax: `.` should only be used to mark index'
                )
            elif len(index) == 1:
                remains = index[0]
            elif len(index) == 2:
                index_num, remains = index
                try:
                    int(index_num)
                except ValueError as e:
                    raise TextLoader.LoadException(
                        f'Invalid index format: {e}'
                    )

            remains = remains.replace('-', '_')
            formatted_name = remains if not index_num else f'{remains}_{index_num}'
            manager.add_object(formatted_name, v)

        manager.update_attributes()
        return manager


class Director:

    # execution write support 0 positional argument and 0 property
    basic_property = { 'duration': 'run_time' }
    animation_controller_mapping = [AnimationGroup, Succession, LaggedStart]

    @dataclass
    class AnimationWithPlayArguments:
        animation: Animation
        execution_cfg: dict[str, Any]

    executions = {
         'write': (Write, 0, {}),
         'unwrite': (Unwrite, 0, {}),
         'create': (Create, 0, {}),
         'uncreate': (Uncreate, 0, {}),
         'transform': (ReplacementTransform, 1, {}),
         'translate': ('shift', 1, {}),
         'scale': ('scale', 1, {}),
         'parallel': (0, 1, {}),
         'succession': (1, -1, {}),
         'lagged': (2, -1, { 'ratio': 'lag_ratio' }),
         'wait': (-1, 1, {})
    }

    @staticmethod
    def _execute_simple(d: 'Director', a: Any, t: str, args: list[Any], kwargs: dict[str, Any], cfg: dict[str, Any]) -> None:
        d.target.play(
            a(d.om.get_object(t), *args, **kwargs),
            **cfg
        )

    @staticmethod
    def _execute_shift(d: 'Director', t: str, args: list[Any], _: dict[str, Any], cfg: dict[str, Any]) -> None:
        assert len(args) == 1, 'Invalid parameters for action `shift`'
        d.target.play(
            getattr(d.om.get_object(t).animate, 'shift')(eval(args[0])),
            **cfg
        )

    @staticmethod
    def _pack_simple(d: 'Director', a: Any, t: str, args: list[Any], kwargs: dict[str, Any], cfg: dict[str, Any]) -> AnimationWithPlayArguments:
        return Director.AnimationWithPlayArguments(
            a(d.om.get_object(t), *args, **kwargs), cfg
        )
        
    class ExecutionException(Exception):
        pass
    
    def __init__(self, om: MObjectManager, action_script: str) -> None:
        self.om = om
        self._action_script_src = action_script
        self.target = None
        self.actions = []

    def set_target_show(self, show: Scene) -> None:
        self.target = show


    def load_actions(self) -> None:
        try:
            actions: dict[str, Any]
            with open(self._action_script_src, 'r', encoding='utf-8') as f:
                actions = json.loads(f.read())

            for k, v in actions.items():
                self.actions.append({
                    'scene': k,
                    'procedure': v
                })
        except Exception as e:
            raise Director.ExecutionException('Failed to load actions from file') from e
        
        pprint.pp(self.actions)

    def generate_action_sequence(self, seq: list[Any]) -> list[AnimationWithPlayArguments]:
        result = []

        for action in seq:
            if 'action' not in action:
                raise Director.ExecutionException('An action must be specified')
            action_name = action['action']
            if action_name not in Director.executions:
                raise Director.ExecutionException(
                    f'Action `{action_name}` is unsupported'
                )
            
            action_object, action_cargs, action_kwargs = Director.executions[action_name]
            cfg = {}
                    
            if isinstance(action_object, int):
                if 'params' not in action:
                    raise Director.ExecutionException('Missing parameters')

                if action_object == -1:
                    if len(action['params']) != 1 or len(action.keys()) != 2:
                        raise Director.ExecutionException('Invalid parameters for action `wait`')
                    result.append(lambda: self.target.wait(action['params'][0]))
                else:
                    for k, v in action.items():
                        if k in ('action', 'target', 'params'):
                            continue
                        elif k in Director.basic_property.keys():
                            cfg[Director.basic_property[k]] = v
                        else:
                            raise Director.ExecutionException(
                                f'Config `{k}` is invalid'
                            )

                    if 'target' in action:
                        raise Director.ExecutionException('Animation controller use params as target')
                    if 'params' not in action:
                        raise Director.ExecutionException('Animation controller needs an animated sequence as paramater')
                    animation_controller = Director.animation_controller_mapping[action_object]
                    result.append(lambda: animation_controller(
                        *self.generate_action_sequence(action['params']),
                        **({} if 'properties' not in action else action['properties'])
                    ), **cfg)

            elif isinstance(action_object, str):
                for k, v in action.items():
                    if k in ('action', 'target', 'params', 'properties'):
                        continue
                    if k in Director.basic_property:
                        cfg[Director.basic_property[k]] = v
                    else:
                        raise Director.ExecutionException(
                            f'Config `{k}` is invalid'
                        )

                if k in Director.basic_property:
                    cfg[Director.basic_property[k]] = v
                else:
                    raise Director.ExecutionException(
                        f'Config `{k}` is invalid'
                    )

                if 'params' not in action:
                    raise Director.ExecutionException('Missing parameters')
                if 'target' not in action:
                        raise Director.ExecutionException('An action target must be specified')
                
                result.append(lambda: getattr(self.__class__, f'_execute_{action_object}')(
                    self, 
                    action['target'],
                    action['params'],
                    {} if 'properties' not in action else action['properties'],
                    cfg
                ))
            else:
                for k, v in action.items():
                    if k in ('action', 'target', 'params', 'properties'):
                        continue
                    if k in Director.basic_property:
                        cfg[Director.basic_property[k]] = v
                    else:
                        raise Director.ExecutionException(
                            f'Config `{k}` is invalid'
                        )

                if 'target' not in action:
                        raise Director.ExecutionException('An action target must be specified')
                
                if action_cargs:
                    if 'params' not in action or len(action['params']) != action_cargs:
                        warnings.warn(f'Unsufficient positional arguments for action `{action_name}`')

                if 'properties' not in action and len(action_kwargs):
                    warnings.warn(f'Missing properties for `{action_name}`')
                
                elif len(action_kwargs):
                    for a in action_kwargs:
                        if a not in action['properties'].keys():
                            warnings.warn(f'Missing property \'{a}\' for `{action_name}`')

                result.append(Director._pack_simple(
                    self,
                    action_object,
                    action['target'],
                    [] if 'params' not in action else action['params'],
                    {} if 'properties' not in action else action['properties'],
                    cfg
                ))  
        return result

    def start_play(self) -> None:
        if self.target is None:
            raise Director.ExecutionException(
                f'Show has not been set'
            )
        
        for scene in self.actions:
            for action in scene['procedure']:
                if 'action' not in action:
                    raise Director.ExecutionException('An action must be specified')
                action_name = action['action']
                if action_name not in Director.executions:
                    raise Director.ExecutionException(
                        f'Action `{action_name}` is unsupported'
                    )
                
                action_object, action_cargs, action_kwargs = Director.executions[action_name]
                cfg = {}
                        
                if isinstance(action_object, int):
                    if 'params' not in action:
                        raise Director.ExecutionException('Missing parameters')

                    if action_object == -1:
                        if len(action['params']) != 1 or len(action.keys()) != 2:
                            raise Director.ExecutionException('Invalid parameters for action `wait`')
                        self.target.wait(action['params'][0])
                    else:
                        for k, v in action.items():
                            if k in ('action', 'target', 'params', 'properties'):
                                continue
                            elif k in Director.basic_property.keys():
                                cfg[Director.basic_property[k]] = v
                            else:
                                raise Director.ExecutionException(
                                    f'Config `{k}` is invalid'
                                )

                        if 'target' in action:
                            raise Director.ExecutionException('Animation controller use parameters as target')
                        if 'params' not in action:
                            raise Director.ExecutionException('Animation controller needs an animated sequence as paramater')
                        animation_controller = Director.animation_controller_mapping[action_object]

                        self.target.play(animation_controller(
                            *[ao.animation for ao in self.generate_action_sequence(action['params'])],
                            **({} if 'properties' not in action else action['properties'])
                        ), **cfg)

                elif isinstance(action_object, str):
                    for k, v in action.items():
                        if k in ('action', 'target', 'params', 'properties'):
                            continue
                        if k in Director.basic_property:
                            cfg[Director.basic_property[k]] = v
                        else:
                            raise Director.ExecutionException(
                                f'Config `{k}` is invalid'
                            )

                    if 'params' not in action:
                        raise Director.ExecutionException('Missing parameters')
                    if 'target' not in action:
                            raise Director.ExecutionException('An action target must be specified')
                    
                    getattr(self.__class__, f'_execute_{action_object}')(
                        self, 
                        action['target'],
                        action['params'],
                        {} if 'properties' not in action else action['properties'],
                        cfg
                    )
                else:
                    for k, v in action.items():
                        if k in ('action', 'target', 'params', 'properties'):
                            continue
                        if k in Director.basic_property:
                            cfg[Director.basic_property[k]] = v
                        else:
                            raise Director.ExecutionException(
                                f'Config `{k}` is invalid'
                            )

                    if 'target' not in action:
                            raise Director.ExecutionException('An action target must be specified')
                    
                    if action_cargs:
                        if 'params' not in action or len(action['params']) != action_cargs:
                            warnings.warn(f'Unsufficient positional arguments for action `{action_name}`')

                    if 'properties' not in action and len(action_kwargs):
                        warnings.warn(f'Missing properties for `{action_name}`')
                    
                    elif len(action_kwargs):
                        for a in action_kwargs:
                            if a not in action['properties'].keys():
                                warnings.warn(f'Missing property \'{a}\' for `{action_name}`')

                    Director._execute_simple(
                        self,
                        action_object,
                        action['target'],
                        [] if 'params' not in action else action['params'],
                        {} if 'properties' not in action else action['properties'],
                        cfg
                    )
