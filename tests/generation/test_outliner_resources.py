from __future__ import annotations

from src.generation.editorial import build_editorial_day_brief
from src.generation.outliner_resources import resolve_passage_cue


def test_resolve_passage_cue_for_luke_net_scene() -> None:
    cue = resolve_passage_cue(
        reference="Luke 5:2-6",
        focus_clause="We worked hard all night and caught nothing",
        scripture_text="Simon answered and said, 'Master, we worked hard all night and caught nothing, but I will do as You say and let down the nets.'",
    )
    assert cue is not None
    assert cue.pastoral_burden == "obedient trust after fruitless labor"


def test_build_editorial_day_brief_uses_outliner_resource_for_luke_5() -> None:
    brief = build_editorial_day_brief(
        day_number=1,
        scripture_reference="Luke 5:2-6",
        scripture_text=(
            "They had gotten out of them and were washing their nets. "
            "Simon answered, 'Master, we worked hard all night and caught nothing, "
            "but I will do as You say and let down the nets.'"
        ),
    )
    assert brief.pastoral_burden == "obedient trust after fruitless labor"
    assert brief.theological_lane == "obedient trust when Christ's word overturns exhausted self-reliance"
    assert brief.application_lane == "obedience that trusts Christ's word more than tired experience"


def test_build_editorial_day_brief_uses_outliner_resource_for_luke_6_sermon() -> None:
    brief = build_editorial_day_brief(
        day_number=8,
        scripture_reference="Luke 6:27-36",
        scripture_text=(
            "But I say to you who hear, love your enemies, do good to those who hate you. "
            "Be merciful, just as your Father is merciful."
        ),
    )
    assert brief.pastoral_burden == "merciful obedience that hears and does Christ's word"
    assert brief.theological_lane == "kingdom obedience shaped by mercy, reversal, and durable hearing"


def test_build_editorial_day_brief_uses_outliner_resource_for_colossians_identity() -> None:
    brief = build_editorial_day_brief(
        day_number=1,
        scripture_reference="Colossians 3:1-3",
        scripture_text=(
            "Therefore if you have been raised up with Christ, keep seeking the things above. "
            "You have died and your life is hidden with Christ in God."
        ),
    )
    assert brief.pastoral_burden == "identity anchored in union with Christ"
    assert brief.theological_lane == "new identity hidden with Christ that reorders desire and attention"


def test_build_editorial_day_brief_uses_outliner_resource_for_colossians_prayer() -> None:
    brief = build_editorial_day_brief(
        day_number=8,
        scripture_reference="Colossians 4:2-4",
        scripture_text=(
            "Devote yourselves to prayer, keeping alert in it with an attitude of thanksgiving; "
            "praying at the same time for us as well, that God will open up to us a door for the word."
        ),
    )
    assert brief.pastoral_burden == "watchful prayer and gospel openness"
    assert brief.application_lane == "alert prayer that seeks gospel opportunity with gratitude instead of passivity"


def test_build_editorial_day_brief_uses_outliner_resource_for_exodus_consecration() -> None:
    brief = build_editorial_day_brief(
        day_number=2,
        scripture_reference="Exodus 19:10-15",
        scripture_text=(
            "Then the Lord also said to Moses, 'Go to the people and consecrate them today "
            "and tomorrow, and let them wash their garments; and let them be ready for the "
            "third day.'"
        ),
    )
    assert brief.pastoral_burden == "reverent preparation before holy encounter"
    assert brief.theological_lane == "holy nearness that requires reverence, consecration, and creaturely boundaries"


def test_build_editorial_day_brief_uses_outliner_resource_for_exodus_commandments() -> None:
    brief = build_editorial_day_brief(
        day_number=7,
        scripture_reference="Exodus 20:1-11",
        scripture_text=(
            "You shall have no other gods before Me. You shall not make for yourself an idol. "
            "You shall not take the name of the Lord your God in vain. Remember the sabbath day, to keep it holy."
        ),
    )
    assert brief.pastoral_burden == "exclusive allegiance to the Lord in worship and trust"
    assert brief.application_lane == "wholehearted worship that rejects rivals, false images, and careless treatment of God's name"


def test_build_editorial_day_brief_uses_outliner_resource_for_proverbs_warning() -> None:
    brief = build_editorial_day_brief(
        day_number=2,
        scripture_reference="Proverbs 1:8-13",
        scripture_text=(
            "My son, if sinners entice you, do not consent. If they say, 'Come with us, "
            "let us lie in wait for blood; let us ambush the innocent without cause.'"
        ),
    )
    assert brief.pastoral_burden == "early refusal of seductive companionship in evil"
    assert brief.theological_lane == "wisdom refuses the first invitation into violence, greed, and shared corruption"


def test_build_editorial_day_brief_uses_outliner_resource_for_proverbs_security() -> None:
    brief = build_editorial_day_brief(
        day_number=6,
        scripture_reference="Proverbs 1:29-33",
        scripture_text=(
            "Whoever listens to me shall live securely and will be at ease from the dread of evil. "
            "Because they hated knowledge and did not choose the fear of the Lord."
        ),
    )
    assert brief.pastoral_burden == "security and treasure for the one who seeks and listens"
    assert brief.application_lane == "diligent listening and seeking that trusts wisdom's safety more than the counterfeit safety of folly"


def test_build_editorial_day_brief_uses_outliner_resource_for_acts_ananias() -> None:
    brief = build_editorial_day_brief(
        day_number=4,
        scripture_reference="Acts 9:10-12",
        scripture_text=(
            "Now there was a disciple at Damascus named Ananias; and the Lord said to him in a vision, "
            "'Ananias.' And he said, 'Here I am, Lord.'"
        ),
    )
    assert brief.pastoral_burden == "Ananias summoned into costly obedience before he understands the whole outcome"
    assert brief.theological_lane == "God often summons obedient servants before all the implications of mercy are visible to them"


def test_build_editorial_day_brief_uses_outliner_resource_for_acts_church_peace() -> None:
    brief = build_editorial_day_brief(
        day_number=9,
        scripture_reference="Acts 9:26-31",
        scripture_text=(
            "Barnabas took hold of him and brought him to the apostles. So the church throughout all Judea "
            "and Galilee and Samaria enjoyed peace, being built up; and going on in the fear of the Lord."
        ),
    )
    assert brief.pastoral_burden == "patient welcome and strengthening peace in the church"
    assert brief.application_lane == "church life that practices discerning welcome and grows stronger through holy fear instead of suspicion or naïveté"


def test_build_editorial_day_brief_uses_outliner_resource_for_acts_restored_fellowship() -> None:
    brief = build_editorial_day_brief(
        day_number=6,
        scripture_reference="Acts 9:17-19",
        scripture_text=(
            "Ananias departed and entered the house, and after laying his hands on him said, "
            "'Brother Saul, the Lord Jesus has sent me.' Something like scales fell from his eyes, "
            "and he got up and was baptized."
        ),
    )
    assert brief.pastoral_burden == "restored sight and received fellowship after mercy arrives"
    assert brief.application_lane == "grateful reception of mercy that accepts both restoration and belonging instead of remaining isolated"


def test_build_editorial_day_brief_uses_outliner_resource_for_acts_tabitha_grief() -> None:
    brief = build_editorial_day_brief(
        day_number=11,
        scripture_reference="Acts 9:36-39",
        scripture_text=(
            "A disciple named Tabitha was abounding with deeds of kindness and charity. "
            "All the widows stood beside him, weeping and showing all the tunics and garments."
        ),
    )
    assert brief.pastoral_burden == "grief that remembers a life of embodied mercy"
    assert brief.theological_lane == "the fellowship of the church remembers mercy in concrete deeds and grieves the loss of faithful love"
