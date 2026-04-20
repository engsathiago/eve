#!/usr/bin/env python3
"""
eve_skill_auto_creator_v108.py — Automatic Skill Creation System
Inspired by EVE-Agent's SkillCreator.

Automatically identifies patterns from completed tasks and creates reusable skills.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

SKILLS_DIR = Path("/memory/skills/auto_created")
DATA_DIR = Path("/root/evolution/data")
DB_PATH = DATA_DIR / "skill_patterns.db"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskPatternStore:
    """
    Store and analyze task patterns for skill creation.
    """

    def __init__(self, db_path: Path = DB_PATH):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                task_hash TEXT NOT NULL UNIQUE,
                task_description TEXT NOT NULL,
                steps TEXT NOT NULL,  -- JSON list
                outcome TEXT,
                success BOOLEAN NOT NULL,
                complexity INTEGER NOT NULL,  -- number of steps
                tools_used TEXT,  -- JSON list
                skill_created BOOLEAN DEFAULT FALSE,
                skill_name TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_complexity ON tasks(complexity);
            CREATE INDEX IF NOT EXISTS idx_tasks_hash ON tasks(task_hash);
            CREATE INDEX NOT EXISTS idx_tasks_success ON tasks(success);

            CREATE TABLE IF NOT EXISTS task_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_hash TEXT UNIQUE NOT NULL,
                task_type TEXT NOT NULL,
                common_steps TEXT NOT NULL,  -- JSON
                frequency INTEGER DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                skill_name TEXT
            );

            CREATE TABLE IF NOT EXISTS skill_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL,
                ts TEXT NOT NULL,
                task_description TEXT,
                success BOOLEAN NOT NULL,
                feedback TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_outcomes_skill ON skill_outcomes(skill_name);
        """)
        self.conn.commit()

    def record_task(self, task_description: str, steps: List[str], 
                    success: bool, tools_used: List[str] = None,
                    outcome: str = "") -> int:
        """Record a completed task for pattern analysis."""
        task_hash = self._hash_task(task_description, steps)
        complexity = len(steps)
        
        cursor = self.conn.execute(
            """INSERT INTO tasks (ts, task_hash, task_description, steps, outcome,
                                  success, complexity, tools_used)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(task_hash) DO UPDATE SET
                   ts = excluded.ts,
                   frequency = frequency + 1""",
            (_utcnow(), task_hash, task_description, json.dumps(steps), outcome,
             success, complexity, json.dumps(tools_used or []))
        )
        self.conn.commit()
        
        # Update patterns
        self._update_patterns(task_description, steps, tools_used or [])
        
        return cursor.lastrowid

    def _hash_task(self, description: str, steps: List[str]) -> str:
        """Create a fingerprint for the task."""
        normalized = re.sub(r'[^\w\s]', '', description.lower())
        content = f"{normalized}:{len(steps)}:{json.dumps(steps)}"
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()[:20]

    def _update_patterns(self, description: str, steps: List[str], tools: List[str]):
        """Extract and update task patterns."""
        task_type = self._classify_task_type(description, tools)
        pattern_hash = self._hash_pattern(task_type, steps)
        
        now = _utcnow()
        self.conn.execute(
            """INSERT INTO task_patterns (pattern_hash, task_type, common_steps, first_seen, last_seen)
               VALUES (?,?,?,?,?)
               ON CONFLICT(pattern_hash) DO UPDATE SET
                   frequency = frequency + 1,
                   last_seen = excluded.last_seen""",
            (pattern_hash, task_type, json.dumps(steps), now, now)
        )
        self.conn.commit()

    def _classify_task_type(self, description: str, tools: List[str]) -> str:
        """Classify task into a type category."""
        desc_lower = description.lower()
        
        if any(t in tools for t in ["file_read", "file_write", "file_list"]):
            return "file_management"
        elif any(t in tools for t in ["web_search", "web_fetch"]):
            return "research"
        elif any(t in tools for t in ["exec", "shell"]):
            return "system_operation"
        elif any(t in tools for t in ["image_generate", "image"]):
            return "content_creation"
        elif "analyze" in desc_lower or "check" in desc_lower:
            return "analysis"
        elif "create" in desc_lower or "generate" in desc_lower:
            return "generation"
        elif "fix" in desc_lower or "repair" in desc_lower:
            return "repair"
        else:
            return "general"

    def _hash_pattern(self, task_type: str, steps: List[str]) -> str:
        """Hash the generalized pattern."""
        generalized = [re.sub(r'[^\w\s]', '', s.lower()[:30]) for s in steps]
        import hashlib
        return hashlib.md5(f"{task_type}:{json.dumps(generalized)}".encode()).hexdigest()[:16]

    def find_recurring_patterns(self, min_frequency: int = 2) -> List[Dict[str, Any]]:
        """Find patterns that occur multiple times (candidates for skills)."""
        rows = self.conn.execute(
            """SELECT task_type, common_steps, frequency, skill_name
               FROM task_patterns WHERE frequency >= ? ORDER BY frequency DESC""",
            (min_frequency,)
        ).fetchall()
        
        return [{
            "task_type": r[0],
            "steps": json.loads(r[1]),
            "frequency": r[2],
            "has_skill": bool(r[3])
        } for r in rows]

    def get_tasks_without_skills(self, min_complexity: int = 3, limit: int = 10) -> List[Dict[str, Any]]:
        """Get successful complex tasks that haven't been turned into skills."""
        rows = self.conn.execute(
            """SELECT task_description, steps, outcome, complexity
               FROM tasks 
               WHERE success=TRUE AND skill_created=FALSE AND complexity >= ?
               ORDER BY complexity DESC LIMIT ?""",
            (min_complexity, limit)
        ).fetchall()
        
        return [{
            "description": r[0],
            "steps": json.loads(r[1]),
            "outcome": r[2],
            "complexity": r[3]
        } for r in rows]


class SkillAutoCreator:
    """
    Automatically creates skills from task patterns.
    """

    def __init__(self, pattern_store: Optional[TaskPatternStore] = None):
        self.store = pattern_store or TaskPatternStore()
        self.skills_dir = SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def maybe_create_skill(self, task_description: str, steps: List[str],
                          outcome: str, tools_used: List[str] = None,
                          force: bool = False) -> Optional[str]:
        """
        Decide if a task should become a skill, and create it if so.
        
        Args:
            task_description: What was done
            steps: List of steps taken
            outcome: Result of the task
            tools_used: Tools that were used
            force: Create skill even if below threshold
        
        Returns:
            Skill name if created, None otherwise
        """
        # Record the task first
        task_id = self.store.record_task(task_description, steps, True, tools_used, outcome)
        
        # Check thresholds
        complexity = len(steps)
        
        # Decision logic
        should_create = force or self._should_create_skill(complexity, task_description, steps)
        
        if not should_create:
            return None
        
        # Generate skill
        skill_name = self._generate_skill_name(task_description)
        skill_content = self._generate_skill_content(
            skill_name, task_description, steps, outcome, tools_used or []
        )
        
        # Save skill
        skill_path = self._save_skill(skill_name, skill_content)
        
        # Update task record
        self.store.conn.execute(
            "UPDATE tasks SET skill_created=TRUE, skill_name=? WHERE id=?",
            (skill_name, task_id)
        )
        self.store.conn.commit()
        
        return skill_name

    def _should_create_skill(self, complexity: int, description: str, steps: List[str]) -> bool:
        """Decision logic for skill creation."""
        # Minimum complexity
        if complexity < 3:
            return False
        
        # Check for recurring patterns
        patterns = self.store.find_recurring_patterns(min_frequency=2)
        for p in patterns:
            if len(p["steps"]) == len(steps):
                return True
        
        # Check if similar task already has skill
        similar = self.store.conn.execute(
            """SELECT COUNT(*) FROM tasks 
               WHERE skill_created=TRUE AND task_description LIKE ?""",
            (f"%{description[:30]}%",)
        ).fetchone()[0]
        
        if similar > 0:
            return False  # Already have skill for similar task
        
        # High complexity tasks are always candidates
        if complexity >= 5:
            return True
        
        return False

    def _generate_skill_name(self, description: str) -> str:
        """Generate a snake_case skill name from description."""
        # Extract key verbs and nouns
        words = re.findall(r'\b\w+\b', description.lower())
        
        # Priority words
        action_words = ["analyze", "check", "create", "generate", "fix", "repair", 
                       "optimize", "search", "fetch", "process", "convert", "build",
                       "deploy", "test", "validate", "sync", "backup", "restore"]
        
        found_actions = [w for w in words if w in action_words]
        
        if found_actions:
            main_action = found_actions[0]
        else:
            main_action = words[0] if words else "task"
        
        # Get object (what is being acted upon)
        object_words = words[1:4] if len(words) > 1 else ["data"]
        
        # Build name
        name_parts = [main_action] + object_words
        name = "_".join(name_parts)[:50]
        name = re.sub(r'[^a-z0-9_]', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        
        # Ensure uniqueness
        counter = 1
        base_name = name
        while (self.skills_dir / f"{name}.md").exists():
            name = f"{base_name}_{counter}"
            counter += 1
        
        return name

    def _generate_skill_content(self, name: str, description: str, steps: List[str],
                                 outcome: str, tools_used: List[str]) -> str:
        """Generate SKILL.md content."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Build steps with tool annotations
        steps_md = []
        for i, step in enumerate(steps, 1):
            # Detect tools used in this step
            step_tools = []
            for tool in tools_used:
                if tool.lower() in step.lower():
                    step_tools.append(f"`{tool}`")
            
            tool_note = f" (uses: {', '.join(step_tools)})" if step_tools else ""
            steps_md.append(f"{i}. {step}{tool_note}")
        
        steps_text = "\n".join(steps_md)
        
        # Generate trigger condition
        trigger = self._extract_trigger(description, steps)
        
        # Extract examples from outcome
        examples = self._extract_examples(outcome)
        examples_md = "\n".join(f"- {e}" for e in examples) if examples else ""
        examples_section = f"\n## Examples\n{examples_md}" if examples else ""
        
        # Detect common failure modes
        failure_modes = self._detect_failure_modes(steps, tools_used)
        notes = f"""
## Notes
Auto-generated from task: "{description[:100]}..."
Outcome: {outcome[:150]}...

### Common Failure Modes
{chr(10).join(f"- {m}" for m in failure_modes) if failure_modes else "- None detected yet"}

### Tools Used
{', '.join(f'`{t}`' for t in tools_used)}
"""
        
        return f"""# {name}
*Created: {ts} | Auto-generated by Eve Skill Creator*

{description}

## When to use
{trigger}

## Steps
{steps_text}
{examples_section}
{notes}
"""

    def _extract_trigger(self, description: str, steps: List[str]) -> str:
        """Extract when to use this skill."""
        # Pattern-based extraction
        patterns = [
            (r'analyze|check|validate', "When you need to analyze or validate {object}"),
            (r'create|generate|build', "When you need to create or generate {object}"),
            (r'fix|repair|resolve', "When {object} has issues that need fixing"),
            (r'search|find|lookup', "When you need to search for or find {object}"),
            (r'fetch|get|retrieve', "When you need to fetch or retrieve {object}"),
            (r'process|transform|convert', "When you need to process or transform {object}"),
        ]
        
        desc_lower = description.lower()
        for pattern, template in patterns:
            if re.search(pattern, desc_lower):
                # Extract object (noun phrase)
                words = re.findall(r'\b\w+\b', description.lower())
                object_words = [w for w in words[1:4] if len(w) > 3]
                obj = " ".join(object_words) if object_words else "data"
                return template.format(object=obj)
        
        return f"When you need to: {description[:80]}"

    def _extract_examples(self, outcome: str) -> List[str]:
        """Extract examples from outcome."""
        examples = []
        
        # Look for file paths, URLs, specific values
        paths = re.findall(r'[\w\-]+\.(?:py|md|json|txt|log)', outcome)
        for p in paths[:2]:
            examples.append(f"Created {p}")
        
        # Look for counts
        counts = re.findall(r'(\d+)\s+(?:files?|items?|records?|results?)', outcome)
        for c in counts[:1]:
            examples.append(f"Processed {c} items")
        
        return examples

    def _detect_failure_modes(self, steps: List[str], tools: List[str]) -> List[str]:
        """Detect potential failure modes from steps."""
        modes = []
        
        step_text = " ".join(steps).lower()
        
        if "file" in step_text or "read" in step_text:
            modes.append("File not found — verify path exists")
        if "web" in step_text or "http" in step_text:
            modes.append("Network timeout — retry with exponential backoff")
        if "exec" in tools or "shell" in step_text:
            modes.append("Permission denied — check if elevated access needed")
        if "json" in step_text or "parse" in step_text:
            modes.append("Malformed data — add validation")
        
        return modes[:3]

    def _save_skill(self, name: str, content: str) -> Path:
        """Save skill to file."""
        skill_path = self.skills_dir / f"{name}.md"
        skill_path.write_text(content, encoding="utf-8")
        return skill_path

    def suggest_skill_improvements(self, skill_name: str) -> List[str]:
        """Suggest improvements based on skill usage."""
        # Get outcomes for this skill
        rows = self.store.conn.execute(
            """SELECT success, feedback FROM skill_outcomes 
               WHERE skill_name=? ORDER BY ts DESC LIMIT 10""",
            (skill_name,)
        ).fetchall()
        
        if not rows:
            return ["No usage data yet — execute skill to gather feedback"]
        
        successes = sum(1 for r in rows if r[0])
        total = len(rows)
        success_rate = successes / total if total > 0 else 0
        
        suggestions = []
        
        if success_rate < 0.7:
            suggestions.append(f"Low success rate ({success_rate:.0%}) — review failure modes")
        
        # Analyze feedback
        feedback_text = " ".join(r[1] or "" for r in rows)
        if "slow" in feedback_text or "timeout" in feedback_text:
            suggestions.append("Consider adding caching or batching")
        if "error" in feedback_text or "fail" in feedback_text:
            suggestions.append("Add more defensive checks")
        
        return suggestions or ["Skill performing well — no changes needed"]

    def get_skill_stats(self) -> Dict[str, Any]:
        """Get statistics on skill creation and usage."""
        total_tasks = self.store.conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]
        
        skills_created = self.store.conn.execute(
            "SELECT COUNT(DISTINCT skill_name) FROM tasks WHERE skill_created=TRUE"
        ).fetchone()[0]
        
        patterns = self.store.conn.execute(
            "SELECT COUNT(*) FROM task_patterns"
        ).fetchone()[0]
        
        recurring = self.store.conn.execute(
            "SELECT COUNT(*) FROM task_patterns WHERE frequency >= 2"
        ).fetchone()[0]
        
        return {
            "total_tasks_recorded": total_tasks,
            "skills_created": skills_created,
            "patterns_identified": patterns,
            "recurring_patterns": recurring,
            "skill_creation_rate": skills_created / total_tasks if total_tasks > 0 else 0
        }


# ── Integration helpers ─────────────────────────────────────────────────────────

class SkillEnhancedExecutor:
    """
    Wraps task execution with automatic skill creation.
    Use this to track and auto-skillify complex tasks.
    """

    def __init__(self, creator: Optional[SkillAutoCreator] = None):
        self.creator = creator or SkillAutoCreator()
        self.current_task: Optional[Dict] = None

    def start_task(self, description: str):
        """Start tracking a new task."""
        self.current_task = {
            "description": description,
            "steps": [],
            "tools": [],
            "start_time": _utcnow()
        }

    def add_step(self, step_description: str, tools_used: List[str] = None):
        """Record a step in the current task."""
        if self.current_task is None:
            return
        
        self.current_task["steps"].append(step_description)
        if tools_used:
            self.current_task["tools"].extend(tools_used)

    def complete_task(self, outcome: str, success: bool = True) -> Optional[str]:
        """
        Complete task and potentially create skill.
        Returns skill name if created.
        """
        if self.current_task is None:
            return None
        
        task = self.current_task
        self.current_task = None
        
        if not success:
            # Still record for learning
            self.creator.store.record_task(
                task["description"], task["steps"], False, task["tools"], outcome
            )
            return None
        
        # Try to create skill
        skill = self.creator.maybe_create_skill(
            task["description"],
            task["steps"],
            outcome,
            list(set(task["tools"]))
        )
        
        return skill


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    creator = SkillAutoCreator()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            print(json.dumps(creator.get_skill_stats(), indent=2))
        elif sys.argv[1] == "patterns":
            patterns = creator.store.find_recurring_patterns(min_frequency=2)
            print(json.dumps(patterns, indent=2))
        elif sys.argv[1] == "test":
            # Simulate task
            creator.start_task("Analyze system logs for errors")
            creator.add_step("List log files in /var/log", ["file_list"])
            creator.add_step("Read recent error logs", ["file_read"])
            creator.add_step("Extract error patterns using regex", ["python_exec"])
            creator.add_step("Generate summary report", ["file_write"])
            
            skill = creator.complete_task("Found 12 errors, report saved to errors.md")
            print(f"Created skill: {skill}" if skill else "No skill created (below threshold)")
            print(json.dumps(creator.get_skill_stats(), indent=2))
    else:
        print("Usage: python eve_skill_auto_creator_v108.py [stats|patterns|test]")
