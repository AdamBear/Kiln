import json

import pytest
from kiln_ai.adapters.eval.base_eval import BaseEval
from kiln_ai.datamodel import BasePrompt, DataSource, DataSourceType
from kiln_ai.datamodel.eval import Eval, EvalConfig
from kiln_ai.datamodel.task import (
    RunConfigProperties,
    Task,
    TaskOutputRatingType,
    TaskRequirement,
    TaskRunConfig,
)


def test_score_schema_five_star():
    # Create a task with a five-star requirement
    task = Task(
        name="Test Task",
        instruction="Test instruction",
        requirements=[
            TaskRequirement(
                name="Quality Score",
                instruction="Rate the quality",
                type=TaskOutputRatingType.five_star,
            )
        ],
    )

    schema_str = BaseEval.build_score_schema(task)
    schema = json.loads(schema_str)

    # Check basic schema structure
    assert schema["type"] == "object"
    assert schema["required"] == ["quality_score", "overall_rating"]

    # Check requirement property, and that it's an enum of 1-5
    req_prop = schema["properties"]["quality_score"]
    assert req_prop["enum"] == [1, 2, 3, 4, 5]
    assert "Quality Score" in req_prop["title"]
    assert "Rate the quality" in req_prop["description"]
    assert "between 1 and 5" in req_prop["description"]

    # Check overall rating property, and that it's an enum of 1-5
    assert "overall_rating" in schema["properties"]
    overall = schema["properties"]["overall_rating"]
    assert overall["enum"] == [1, 2, 3, 4, 5]
    assert "Overall Rating" in overall["title"]
    assert "The overall rating for the task output" in overall["description"]
    assert "between 1 and 5" in overall["description"]


def test_score_schema_five_star_float():
    # Create a task with a five-star requirement
    task = Task(
        name="Test Task",
        instruction="Test instruction",
        requirements=[
            TaskRequirement(
                name="Quality Score",
                instruction="Rate the quality",
                type=TaskOutputRatingType.five_star,
            )
        ],
    )

    schema_str = BaseEval.build_score_schema(task, allow_float_scores=True)
    schema = json.loads(schema_str)

    # Check basic schema structure
    assert schema["type"] == "object"
    assert schema["required"] == ["quality_score", "overall_rating"]

    # Check requirement property
    req_prop = schema["properties"]["quality_score"]
    assert req_prop["type"] == "number"
    assert req_prop["minimum"] == 1
    assert req_prop["maximum"] == 5
    assert "Quality Score" in req_prop["title"]
    assert "Rate the quality" in req_prop["description"]
    assert "between 1 and 5" in req_prop["description"]

    # Check overall rating property
    assert "overall_rating" in schema["properties"]
    overall = schema["properties"]["overall_rating"]
    assert overall["type"] == "number"
    assert overall["minimum"] == 1
    assert overall["maximum"] == 5
    assert "Overall Rating" in overall["title"]
    assert "The overall rating for the task output" in overall["description"]
    assert "between 1 and 5" in overall["description"]


def test_score_schema_pass_fail():
    task = Task(
        name="Test Task",
        instruction="Test instruction",
        requirements=[
            TaskRequirement(
                name="Pass Fail Test",
                instruction="Check if it passes",
                type=TaskOutputRatingType.pass_fail,
            )
        ],
    )

    schema_str = BaseEval.build_score_schema(task)
    schema = json.loads(schema_str)

    req_prop = schema["properties"]["pass_fail_test"]
    assert req_prop["enum"] == ["pass", "fail"]
    assert "Pass Fail Test" in req_prop["title"]
    assert "Check if it passes" in req_prop["description"]
    assert "'pass' or 'fail'" in req_prop["description"]

    assert schema["properties"]["overall_rating"] is not None

    # Now check that we can allow float scores with the proper float structure
    schema_str = BaseEval.build_score_schema(task, allow_float_scores=True)
    schema = json.loads(schema_str)

    req_prop = schema["properties"]["pass_fail_test"]
    assert req_prop["type"] == "number"
    assert req_prop["minimum"] == 0
    assert req_prop["maximum"] == 1
    assert (
        "between 0 and 1, with 0 being a failure and 1 being a pass"
        in req_prop["description"]
    )


def test_score_schema_pass_fail_critical():
    task = Task(
        name="Test Task",
        instruction="Test instruction",
        requirements=[
            TaskRequirement(
                name="Critical Test",
                instruction="Check for critical issues",
                type=TaskOutputRatingType.pass_fail_critical,
            )
        ],
    )

    schema_str = BaseEval.build_score_schema(task)
    schema = json.loads(schema_str)

    req_prop = schema["properties"]["critical_test"]
    assert "enum" in req_prop
    assert req_prop["enum"] == ["pass", "fail", "critical"]
    assert "'pass', 'fail', or 'critical'" in req_prop["description"]

    assert schema["properties"]["overall_rating"] is not None

    # Now check that we can allow float scores with the proper float structure
    schema_str = BaseEval.build_score_schema(task, allow_float_scores=True)
    schema = json.loads(schema_str)

    req_prop = schema["properties"]["critical_test"]
    assert req_prop["type"] == "number"
    assert req_prop["minimum"] == -1
    assert req_prop["maximum"] == 1
    assert "between -1 and 1, with 1 being a pass" in req_prop["description"]


def test_score_schema_multiple_requirements():
    task = Task(
        name="Test Task",
        instruction="Test instruction",
        requirements=[
            TaskRequirement(
                name="Quality",
                instruction="Rate quality",
                type=TaskOutputRatingType.five_star,
            ),
            TaskRequirement(
                name="Pass Check",
                instruction="Basic pass check",
                type=TaskOutputRatingType.pass_fail,
            ),
            TaskRequirement(
                name="Security",
                instruction="Check security",
                type=TaskOutputRatingType.pass_fail_critical,
            ),
        ],
    )

    schema_str = BaseEval.build_score_schema(task)
    schema = json.loads(schema_str)

    # Verify order is maintained
    assert list(schema["properties"].keys()) == [
        "quality",
        "pass_check",
        "security",
        "overall_rating",
    ]


def test_score_schema_custom_type_skipped():
    task = Task(
        name="Test Task",
        instruction="Test instruction",
        requirements=[
            TaskRequirement(
                name="Custom Rating",
                instruction="Custom rating",
                type=TaskOutputRatingType.custom,
            ),
            TaskRequirement(
                name="Quality",
                instruction="Rate quality",
                type=TaskOutputRatingType.five_star,
            ),
        ],
    )

    schema_str = BaseEval.build_score_schema(task)
    schema = json.loads(schema_str)

    # Custom type should be skipped
    assert len(schema["properties"]) == 2  # one requirement + overall_rating

    # Verify only non-custom requirement and overall_rating are present
    props = list(schema["properties"].keys())
    assert "quality" in props
    assert "overall_rating" in props


def test_score_schema_no_requirements():
    task = Task(name="Test Task", instruction="Test instruction", requirements=[])

    schema_str = BaseEval.build_score_schema(task)
    schema = json.loads(schema_str)

    # Should only have overall_rating
    assert len(schema["properties"]) == 1
    assert "overall_rating" in schema["properties"]


class TestEval(BaseEval):
    """Test implementation of BaseEval"""

    async def run_eval(self, task_run):
        return {"overall_rating": 5, "quality": 4}


@pytest.mark.paid
@pytest.mark.asyncio
async def test_run_method():
    task = Task(
        name="Test Task",
        instruction="Test instruction",
        requirements=[
            TaskRequirement(
                name="Quality",
                instruction="Rate quality",
                type=TaskOutputRatingType.five_star,
            )
        ],
    )

    eval_config = EvalConfig(
        name="Test Eval Config",
        model=DataSource(
            type=DataSourceType.synthetic,
            properties={
                "model_name": "gpt-4o",
                "model_provider": "openai",
                "adapter_name": "test",
            },
        ),
        parent=Eval(
            name="Test Eval",
            parent=task,
            eval_set_filter_id="all",
            eval_configs_filter_id="all",
        ),
        prompt=BasePrompt(
            name="Test Prompt",
            prompt="Test prompt",
        ),
        properties={"eval_steps": ["test_step"]},
    )

    run_config = TaskRunConfig(
        name="Test Run Config",
        run_config_properties=RunConfigProperties(
            model_name="llama_3_1_8b",
            model_provider_name="groq",
            prompt_id="simple_prompt_builder",
        ),
        parent=task,
    )

    evaluator = TestEval(eval_config, run_config.run_config())

    # Run the evaluation
    task_run, eval_scores = await evaluator.run("test input")

    # Verify task run was created
    assert task_run.input == "test input"
    assert isinstance(task_run.output.output, str)

    # Verify eval scores match schema and contain expected values
    assert eval_scores["overall_rating"] == 5
    assert eval_scores["quality"] == 4

    # Verify schema validation worked (these keys should exist per schema)
    assert set(eval_scores.keys()) == {"overall_rating", "quality"}
