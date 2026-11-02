# Starting a robot design session

Copy one of the messages below into a **new chat in the Claude Code desktop app, opened in this project folder**. Fill in the brackets and delete what you don't need. Claude loads the `ftc-robot-design` skill from it. It then talks design with you and searches the knowledge base, and **doesn't change Onshape until you say "CAD …"**.

## Before you start (once per day)
- The `onshape` MCP server is registered (see README → Install) and `ONSHAPE_API_KEY` / `ONSHAPE_API_SECRET` are set.
- API budget: 2,500 calls per year; check the count at the top of `Status.md`.

---

## 1. New robot
```
We're designing a new FTC robot for [BIOBUZZ 2026-27]. Call it [bb1].
Game goals we care about: [e.g. score POLLEN in the HIVE fast, hang at the end].
Subsystems I'm thinking of: [drivetrain, intake, transfer, shooter, turret].
Constraints and preferences: [e.g. goBILDA + laser-cut wood/aluminum + FDM, keep it under 8 motors, no swerve].
Start with the robot kickoff (spaces and motor/servo budget per subsystem), then let's talk about the [shooter] first.
```

## 2. Work on one subsystem (any later chat)
```
Let's work on the [shooter] of robot [bb1].
It needs to: [e.g. shoot POLLEN from 1–3 m, adjustable angle, fire 3 balls in under 2 s].
Watch out for: [e.g. weight on the turret, belt slip, ball jams at the feed].
Old version / reference: [Onshape link or path to a STEP file, or "none"].
Space it has to fit in: [e.g. "what the design file says", or 300 × 250 × 200 mm above the drivetrain].
[Optional: paste a sketch or whiteboard photo.]
```

## 3. When the design is agreed
```
CAD the [shooter].
```
Before modeling each custom part Claude shows you a short **constraint card** (job, how it's fastened, what supports and retains each shaft/pin, envelope, print setup, what sets its size, top-team reference). Correct it there: it's cheaper than fixing the CAD. Cards are kept in `kb/designs/<robot>/cards/`.

The main chat (Opus) then hands the cards to a **Sonnet `cad-builder`** subagent, and an Opus **`cad-reviewer`** checks the result; you only see the builder's report and the review. At the end it shows you a short reviewed card of what the builder learned, and that card enters the knowledge base only when you say OK.

or, to build every agreed subsystem (drivetrain first):
```
CAD the robot.
```

## 4. Verdicts while it builds
Claude can't call a subsystem built until an independent **cad-reviewer** agent (it hasn't seen the chat) has reviewed the CAD and its blockers are fixed or you accepted them. You get its should-fix list with the result. To re-run it any time: `Run the cad-reviewer on the [shooter].`
- Accept: `Looks good, accept the [shooter].`
- Send back: `Not this: [what's wrong, and why]. Try [what instead].`
- The reason matters: Claude records it with the KB entries it came from, so later designs rank them up or down.

## 5. End of the chat
```
Wrap up: save the session card, with action items for anything that needs coding or fixing.
```
Lessons meant for every robot wait for your OK. Later: `Show me the pending lessons.` Open action items are in `kb/action-items.md`.

If you'd rather have an agent write the card later, first ask `What's this session's ID?`, then give the agent: `Follow docs/plans/session-ingest-brief.md for session <id>.`

---

## Other useful openers
- **Tolerance results:** `Here are my print test results: [paste the filled-in table from tolerance-tests/print/README.md]. Update the design rules.` (Same for `tolerance-tests/laser/README.md`.)
- **Just ask the knowledge base:** `What do the top teams use for [turrets]? Show the best 3 with their key numbers.`
- **Check the robot:** `Run the robot checks on [bb1]: start cube, extended size, motors and servos, interference.`
