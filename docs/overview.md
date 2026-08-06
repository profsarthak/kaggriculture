# What this project is, in plain English

Draft for the public README. Written for someone who has never seen the competition.

## The game

Kaggriculture is a farming game played between two competitors over thirty in-game days. You
plant crops, raise animals, hire help, and sell what you produce. Whoever has more money at the
end wins.

The twist is that **you never play it yourself.** You write a program, upload it, and Kaggle
runs it against other people's programs thousands of times. Your program gets the state of the
board each turn — where your workers are, what's growing, what things are selling for — and has
to decide what everyone does next. It makes that decision 720 times per game, in under a
second each time.

So the work is not "get good at a farming game." It is "work out what good play *is*, then
write something that does it reliably without you there."

## The decision that shaped everything

The obvious way to start is to write something that works and then fiddle with it until it
scores better. We didn't do that. The instinct was: *this is a strategic interaction with a
payoff, so model it properly first, then write code that implements the answer.*

That was mostly right, and one part of it was wrong, and the distinction turned out to matter.

**Wrong:** you cannot "solve" this game. Chess-style solving works when you can enumerate the
possibilities. Here there are 720 turns, both players move simultaneously, you can't see
everything your opponent has, and on any given turn there are millions of possible action
combinations. Nobody can compute the optimal strategy for that, and claiming otherwise would be
false.

**Right:** the *economics* can be worked out exactly. And that turned out to be where nearly all
the value was.

## Phase A: reading the rulebook properly

Kaggle publishes the game's source code. Rather than infer the rules by playing, we read them.

### The market is the whole game

Prices are not fixed. Every product has a price that **falls as you sell more of it.** Each one
has a formula, and once you extract the formula you can calculate exactly how much you can sell
before the price collapses to $1 — the point where selling more is pointless.

We called that a product's **pool**. The results were not what the game's own documentation
suggests:

| product | how much you can sell before the price dies |
|---|---|
| Wheat, Eggs | effectively unlimited |
| Melon | about 158 units — worth ~$26,000 |
| Milk | about 76 units |
| Wool | about 59 units |
| Strawberry | about 62 units — the *whole season's* worth is under $4,000 |

Strawberry has one of the highest sticker prices in the game. Its entire season is worth less
than a day of egg production. **Sticker price tells you almost nothing; pool depth tells you
almost everything.** That single finding redirected the entire strategy.

### The pools are shared

Here is where it becomes a game rather than a puzzle. Both players sell into the *same* market.
If your opponent sells 100 melons, the price you get for yours is lower. So the finite pools are
a race.

We worked out the melon race exactly. Two players harvesting at the same time split it, roughly
$13,000 each. **One player selling before the other takes almost the whole thing — $26,000
against $459.** Melon takes ten days to grow, so this is decided by what you plant on day one
and cannot be recovered later.

That is a genuine game-theory result: a first-mover advantage worth more than most of the rest
of the plan combined.

### What is actually scarce?

The answer changed three times, and each change rewrote the strategy.

First we thought **land**. Then a proper calculation said **worker time** — you can buy more
land than your workers can tend. Then we measured the real agent and found workers were spending
**71% of their turns walking between tiles**, so the true constraint was neither: it was how
efficiently workers moved.

Each answer was reasonable given what we knew. Each was wrong until measured.

## Phase B: building something that plays

The agent works on a simple principle. Each turn it lists every job that wants doing — this
plant needs water, that animal needs feeding, this tile is empty — ranks them, and assigns
workers to the best ones. Jobs that are *irreversible if missed* rank highest: an unwatered
plant dies, an unfed animal escapes permanently, and no amount of money later undoes either.

The first version scored 6,704. The current one scores around 75,000.

Almost none of that came from clever tactics. It came from three things:

**Cows.** Milk sells for three times what eggs do and almost nobody else was producing it. Worth
about +11,700 on its own.

**Letting workers finish a journey.** The agent originally re-decided every worker's job every
single turn, so a worker three steps into a five-step walk could be sent somewhere else and the
walk wasted. Making them commit to a destination was worth +6,400.

**Hiring to demand.** We were paying a full crew from day one, when there was nothing for them
to do — 81% of worker time was idle on day six, because the farm was limited by *money*, not
hands. Scaling the crew to the available work was worth +3,400.

## The part that nearly ruined it: we were measuring wrong

This is the most transferable lesson in the project.

**We were testing against a punching bag.** Every improvement was validated by beating the
game's built-in practice opponent. That opponent finishes on about 3,500 coins. Real competitors
finish on 40,000+. Beating it 15 times out of 15 told us *nothing*, and every tuning decision
made against it was suspect.

**Our comparisons were biased.** We always tested the new version as "player 1" against the old
as "player 2". It turns out player 1 has a small built-in advantage. So we were partly measuring
the seat rather than the change. Fixing it — playing every matchup twice with the sides swapped
— cut the noise so much that a test that used to need dozens of games now needs three.

**We counted draws as losses.** The agent is completely deterministic, so a change that doesn't
trigger produces an identical game — a tie. Counting those as failures made a genuinely 50/50
change look like a disaster.

Each of these was invisible until specifically checked. None produced an error message.

## Silent failure, and the signature that catches it

The game never tells you an action failed. Feed an animal with no food in hand and nothing
happens — no error, no warning, just an animal that quietly starves two days later and a
slightly lower score.

We shipped a version where **the entire animal operation never ran.** Animals were bought and
left sitting in storage, because placing one takes it from a worker's hands and we only ever
checked the warehouse. Fourteen empty barns per game. The score was climbing at the time, so
nothing looked wrong.

The tell, which has now caught four separate bugs: **a setting that changes nothing produces
identical results, not slightly different ones.** Real effects wobble. Perfect repetition across
different settings means the setting isn't connected to anything. We now treat a suspiciously
flat result as a bug report.

## The deepest lesson: answers expire

Early on, the game theory said the right melon commitment was 8 tiles, given what else you could
do with a tile. We tested it, and 8 was right.

It is now 5, and going lower would probably be better still.

Nothing about melon changed. What changed is the *alternative*. Once cows became productive, a
tile spent on melon costs you a cow, and cows got much better. The original answer was correct
about the game and correct at the time — it was a statement about one particular farm's
trade-offs, and those trade-offs moved.

The same thing happened to almost every number we derived. This is not a failure of the method;
it is what the method is for. But it means **a derived answer has a shelf life**, and re-deriving
periodically is part of the work rather than a sign something went wrong.

## Honest accounting

Things we tried that did not work, each of which looked obviously right beforehand: buying
animal feed instead of growing it; opening with a faster-growing crop, which the strongest
opponent we faced actually does; using our free fertiliser on crops; giving each worker their
own territory; pacing sales to avoid crashing prices; putting the animals nearest the barn;
adapting our melon planting to the opponent's; taking deliberate risks when losing.

Eight structural ideas, all measured, all rejected. That is not wasted effort — each one is
now a documented dead end that nobody needs to try again, and several taught us something about
why the game works the way it does.

## Where it stands

The agent scores roughly 75,000 against the practice opponent and holds a positive record on the
live leaderboard. Against real competitors we average about 87% of their scores — genuinely
competitive, not yet leading.

Parameter tuning is exhausted: an automated search that walks every setting up and down finds
nothing left to improve. The remaining gap looks like execution capacity rather than strategy.

## What a non-specialist should take from this

1. **Understand the system before optimising it.** The market analysis took a day and redirected
   everything. No amount of trial and error would have revealed that strawberries are worthless.
2. **Check your ruler before trusting your measurements.** We spent real effort optimising
   against a benchmark that could not distinguish good from bad.
3. **Silence is not success.** In any system that fails quietly, absence of errors means nothing.
4. **Write down what didn't work, and why.** Half of this repository is negative results, and
   they are the part most likely to save someone time.
5. **Expect your conclusions to expire.** They were answers about a system, and the system moved.
