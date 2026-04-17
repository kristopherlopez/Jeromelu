# Skill Creator Agents

Located at `.claude/skills/skill-creator/agents/`. Used by the `/skill-creator` skill for evaluating and improving Claude Code skills.

## Blind Comparator

| | |
|---|---|
| **File** | `agents/comparator.md` |
| **Purpose** | A/B compare two skill outputs without knowing which skill produced them |
| **Method** | Generate evaluation rubric (content + structure dimensions, 1–5 scale), score both outputs, determine winner |
| **Output** | `{winner, reasoning, rubric_scores, output_quality, expectation_results}` |

## Post-hoc Analyzer

| | |
|---|---|
| **File** | `agents/analyzer.md` |
| **Purpose** | Analyze WHY a skill output won or lost; extract improvement suggestions |
| **Input** | Comparison result + both skills + both execution transcripts |
| **Output** | `{comparison_summary, winner_strengths, loser_weaknesses, instruction_following (1-10), improvement_suggestions}` |

Also supports a **Benchmark Analyzer** mode for cross-eval pattern analysis.

## Grader

| | |
|---|---|
| **File** | `agents/grader.md` |
| **Purpose** | Evaluate skill output against expectations; extract and verify implicit claims |
| **Input** | Expectations + execution transcript + output files |
| **Output** | `{expectations[PASS/FAIL], summary, execution_metrics, claims, eval_feedback}` |
