from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PassageCue:
    books: tuple[str, ...]
    contains_any: tuple[str, ...]
    pastoral_burden: str
    theological_lane: str
    application_lane: str


LUKE_5_6_CUES: tuple[PassageCue, ...] = (
    PassageCue(
        books=("luke",),
        contains_any=(
            "worked hard all night and caught nothing",
            "put out into the deep water",
            "let down your nets for a catch",
            "at your word i will let down the nets",
        ),
        pastoral_burden="obedient trust after fruitless labor",
        theological_lane="obedient trust when Christ's word overturns exhausted self-reliance",
        application_lane="obedience that trusts Christ's word more than tired experience",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "depart from me for i am a sinful man",
            "do not fear, from now on you will be catching men",
            "stretched out his hand and touched him",
            "i am willing; be cleansed",
        ),
        pastoral_burden="cleansing mercy for the unworthy",
        theological_lane="holy mercy that draws near to the unworthy and the unclean",
        application_lane="humble nearness to Christ that receives cleansing mercy without hiding need",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "he himself would often slip away to the wilderness and pray",
            "your sins have been forgiven you",
            "which is easier, to say",
            "get up and walk",
        ),
        pastoral_burden="forgiving authority revealed through prayerful dependence",
        theological_lane="forgiving authority exercised in prayerful dependence",
        application_lane="confident faith that brings real need to Christ's forgiving authority",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "follow me",
            "he left everything behind",
            "i have not come to call the righteous but sinners to repentance",
            "the disciples of john often fast",
            "when the bridegroom is taken away",
            "new wine must be put into fresh wineskins",
        ),
        pastoral_burden="new allegiance demanded by Christ's presence",
        theological_lane="new allegiance demanded by the presence of Christ",
        application_lane="wholehearted response that leaves lesser loyalties behind for Christ",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "that they might find reason to accuse him",
            "is it lawful to do good or to do harm on the sabbath",
            "he chose twelve of them",
            "stood on a level place",
        ),
        pastoral_burden="kingdom mercy confronting hardened religion",
        theological_lane="kingdom mercy and authority confronting hardened religion",
        application_lane="merciful obedience that values people over performative religion",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "blessed are you who are poor",
            "love your enemies",
            "lend, expecting nothing in return",
            "be merciful, just as your father is merciful",
            "why do you call me, 'lord, lord,' and do not do what i say",
            "dug deep and laid a foundation on the rock",
        ),
        pastoral_burden="merciful obedience that hears and does Christ's word",
        theological_lane="kingdom obedience shaped by mercy, reversal, and durable hearing",
        application_lane="concrete mercy and durable obedience that actually does what Christ says",
    ),
)

COLOSSIANS_3_4_CUES: tuple[PassageCue, ...] = (
    PassageCue(
        books=("colossians",),
        contains_any=(
            "you have died and your life is hidden with christ in god",
            "keep seeking the things above",
            "set your mind on the things above",
        ),
        pastoral_burden="identity anchored in union with Christ",
        theological_lane="new identity hidden with Christ that reorders desire and attention",
        application_lane="set the mind and affections according to union with Christ rather than earthly dominance",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "consider the members of your earthly body as dead",
            "immorality",
            "evil desire",
            "greed, which amounts to idolatry",
            "on account of these the wrath of god will come",
        ),
        pastoral_burden="mortification of earthly desire under Christ's lordship",
        theological_lane="sin put to death because the old order no longer rules those in Christ",
        application_lane="serious repentance that treats idolatrous desire as something to kill, not manage",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "put them all aside",
            "anger, wrath, malice",
            "do not lie to one another",
            "laid aside the old self",
            "put on the new self",
        ),
        pastoral_burden="putting off corrupt relational habits",
        theological_lane="the new self rejects corrosive speech and falsehood as part of real renewal",
        application_lane="truthful speech and relational repentance that match the new self",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "there is no distinction between greek and jew",
            "christ is all, and in all",
            "put on a heart of compassion",
            "bearing with one another",
            "put on love",
        ),
        pastoral_burden="new-community life shaped by Christ's reconciling fullness",
        theological_lane="a renewed people made one in Christ and clothed with love",
        application_lane="patient, forgiving, love-governed community life that fits Christ's new humanity",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "let the peace of christ rule",
            "let the word of christ richly dwell within you",
            "teaching and admonishing one another",
            "psalms and hymns and spiritual songs",
            "whatever you do in word or deed",
        ),
        pastoral_burden="church life ruled by Christ's peace and word",
        theological_lane="worship, gratitude, and mutual instruction under the ruling peace and word of Christ",
        application_lane="gathered and daily life shaped by gratitude, Christ's word, and worshipful obedience",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "wives, be subject",
            "husbands, love your wives",
            "children, be obedient",
            "fathers, do not exasperate your children",
        ),
        pastoral_burden="household life ordered under the Lordship of Christ",
        theological_lane="ordinary household relationships brought under Christ's good authority",
        application_lane="household faithfulness that refuses harshness, resentment, and disorder under Christ's lordship",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "slaves, in all things obey",
            "fearing the lord",
            "it is the lord christ whom you serve",
            "he who does wrong will receive the consequences",
            "grant to your slaves justice and fairness",
        ),
        pastoral_burden="ordinary work and authority rendered answerable to Christ",
        theological_lane="daily labor and authority transformed by the reality that Christ is the true master",
        application_lane="integrity in work and fairness in authority because every station answers to Christ",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "devote yourselves to prayer",
            "keeping alert in it with an attitude of thanksgiving",
            "pray for us as well",
            "open up to us a door for the word",
        ),
        pastoral_burden="watchful prayer and gospel openness",
        theological_lane="watchful thanksgiving that labors for open doors for the gospel",
        application_lane="alert prayer that seeks gospel opportunity with gratitude instead of passivity",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "conduct yourselves with wisdom toward outsiders",
            "making the most of the opportunity",
            "let your speech always be with grace",
            "seasoned as it were with salt",
        ),
        pastoral_burden="wise witness in public speech and conduct",
        theological_lane="public wisdom and gracious speech that make the gospel fittingly visible",
        application_lane="public conduct and speech marked by grace, wisdom, and timely witness",
    ),
    PassageCue(
        books=("colossians",),
        contains_any=(
            "tychicus",
            "onesimus",
            "archippus",
            "remember my imprisonment",
            "grace be with you",
        ),
        pastoral_burden="ordinary ministry faithfulness in the fellowship of the gospel",
        theological_lane="gospel partnership expressed through ordinary names, duties, and remembered suffering",
        application_lane="steady faithfulness in ordinary ministry roles while honoring the cost of gospel service",
    ),
)

EXODUS_19_20_CUES: tuple[PassageCue, ...] = (
    PassageCue(
        books=("exodus",),
        contains_any=(
            "you yourselves have seen what i did to the egyptians",
            "i bore you on eagles' wings",
            "if you will indeed obey my voice and keep my covenant",
            "you shall be my own possession among all the peoples",
        ),
        pastoral_burden="covenant identity grounded in redeeming grace",
        theological_lane="redeeming grace that brings a people near before covenant obedience is required",
        application_lane="obedience that remembers God's redeeming grace before treating holiness as self-made achievement",
    ),
    PassageCue(
        books=("exodus",),
        contains_any=(
            "consecrate them today and tomorrow",
            "let them wash their garments",
            "be ready for the third day",
            "set bounds for the people all around",
        ),
        pastoral_burden="reverent preparation before holy encounter",
        theological_lane="holy nearness that requires reverence, consecration, and creaturely boundaries",
        application_lane="reverent readiness that does not treat God's holiness casually or presumptuously",
    ),
    PassageCue(
        books=("exodus",),
        contains_any=(
            "there were thunder and lightning flashes",
            "mount sinai was wrapped in smoke",
            "the whole mountain quaked violently",
            "the sound of the trumpet grew louder and louder",
        ),
        pastoral_burden="holy awe before the God who descends in majesty",
        theological_lane="divine majesty that shakes human certainty and calls forth trembling reverence",
        application_lane="worshipful fear that receives God's holiness without reducing him to something manageable",
    ),
    PassageCue(
        books=("exodus",),
        contains_any=(
            "you shall have no other gods before me",
            "you shall not make for yourself an idol",
            "you shall not take the name of the lord your god in vain",
            "remember the sabbath day, to keep it holy",
        ),
        pastoral_burden="exclusive allegiance to the Lord in worship and trust",
        theological_lane="covenant life ordered by exclusive allegiance to the Lord and holy worship",
        application_lane="wholehearted worship that rejects rivals, false images, and careless treatment of God's name",
    ),
    PassageCue(
        books=("exodus",),
        contains_any=(
            "honor your father and your mother",
            "you shall not murder",
            "you shall not commit adultery",
            "you shall not steal",
            "you shall not bear false witness",
            "you shall not covet",
        ),
        pastoral_burden="neighbor love expressed through covenant-shaped restraint",
        theological_lane="love of neighbor protected by God's commands against violence, deceit, and grasping desire",
        application_lane="concrete neighbor-love that refuses harm, falsehood, and covetous grasping",
    ),
    PassageCue(
        books=("exodus",),
        contains_any=(
            "do not let god speak to us, or we will die",
            "do not be afraid; for god has come in order to test you",
            "that the fear of him may remain with you",
        ),
        pastoral_burden="fear of God that restrains sin without driving us away from him",
        theological_lane="holy fear meant to keep a people from sin, not to leave them in faithless terror",
        application_lane="humble fear of God that leads to obedience instead of shrinking back into unbelief",
    ),
)

PROVERBS_1_2_CUES: tuple[PassageCue, ...] = (
    PassageCue(
        books=("proverbs",),
        contains_any=(
            "the fear of the lord is the beginning of knowledge",
            "to know wisdom and instruction",
            "fools despise wisdom and instruction",
        ),
        pastoral_burden="wisdom begins with reverent teachability before the Lord",
        theological_lane="true wisdom starts in reverent submission to the Lord rather than self-assured cleverness",
        application_lane="humble teachability that receives wisdom as the Lord's gift rather than personal possession",
    ),
    PassageCue(
        books=("proverbs",),
        contains_any=(
            "do not consent",
            "come with us",
            "let us lie in wait for blood",
            "we shall find all kinds of precious wealth",
        ),
        pastoral_burden="early refusal of seductive companionship in evil",
        theological_lane="wisdom refuses the first invitation into violence, greed, and shared corruption",
        application_lane="prompt refusal that names sinful companionship as dangerous before it hardens into shared evil",
    ),
    PassageCue(
        books=("proverbs",),
        contains_any=(
            "their feet run to evil",
            "these men lie in wait for their own blood",
            "so are the ways of everyone who gains by violence",
        ),
        pastoral_burden="seeing the self-destruction hidden inside greedy violence",
        theological_lane="violent greed becomes a trap that turns back on those who love it",
        application_lane="discernment that looks past the thrill of gain and sees the ruin that greedy paths finally bring",
    ),
    PassageCue(
        books=("proverbs",),
        contains_any=(
            "wisdom shouts in the street",
            "turn to my reproof",
            "i will pour out my spirit on you",
            "i will make my words known to you",
        ),
        pastoral_burden="hearing wisdom's public call before it is too late",
        theological_lane="wisdom openly calls the simple to turn, receive reproof, and live",
        application_lane="responsive listening that does not despise public correction or delay turning while wisdom still calls",
    ),
    PassageCue(
        books=("proverbs",),
        contains_any=(
            "because i called and you refused",
            "they will eat of the fruit of their own way",
            "they will call on me, but i will not answer",
        ),
        pastoral_burden="the bitter cost of refusing wisdom's warning",
        theological_lane="refused wisdom leaves the stubborn to the consequences of the way they chose",
        application_lane="softened responsiveness that takes warning seriously before stubbornness becomes its own judgment",
    ),
    PassageCue(
        books=("proverbs",),
        contains_any=(
            "whoever listens to me shall live securely",
            "will be at ease from the dread of evil",
            "if you receive my words",
            "seek her as silver",
        ),
        pastoral_burden="security and treasure for the one who seeks and listens",
        theological_lane="the Lord gives guarded security and true understanding to those who seek wisdom as treasure",
        application_lane="diligent listening and seeking that trusts wisdom's safety more than the counterfeit safety of folly",
    ),
    PassageCue(
        books=("proverbs",),
        contains_any=(
            "the lord gives wisdom",
            "he stores up sound wisdom for the upright",
            "he is a shield to those who walk in integrity",
            "discretion will guard you",
        ),
        pastoral_burden="wisdom given and guarded by the Lord",
        theological_lane="wisdom is not self-manufactured; it is given and guarded by the Lord for upright walking",
        application_lane="dependent pursuit that asks, receives, and walks under the Lord's guarding wisdom",
    ),
    PassageCue(
        books=("proverbs",),
        contains_any=(
            "to deliver you from the way of evil",
            "from the man who speaks perverse things",
            "to deliver you from the strange woman",
            "so you will walk in the way of good men",
        ),
        pastoral_burden="wisdom delivers from crooked voices and keeps the feet on a good path",
        theological_lane="the Lord's wisdom rescues from crooked speech, seductive unfaithfulness, and ruined paths",
        application_lane="path-aware obedience that lets wisdom expose twisted voices and keep the feet among the upright",
    ),
)

ACTS_9_CUES: tuple[PassageCue, ...] = (
    PassageCue(
        books=("acts",),
        contains_any=(
            "still breathing threats and murder",
            "letters to the synagogues at damascus",
            "suddenly a light from heaven flashed around him",
        ),
        pastoral_burden="hostile zeal exposed on the road of self-assured violence",
        theological_lane="hostile zeal can look purposeful and religious even while it is marching against the Lord's people",
        application_lane="honest self-examination that stops baptizing harshness and hostility as righteous purpose",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "saul, saul, why are you persecuting me",
            "i am jesus whom you are persecuting",
            "what shall i do, lord",
        ),
        pastoral_burden="hostile pride shattered by the risen Lord",
        theological_lane="the risen Lord confronts hostile zeal and exposes persecution of his people as opposition to himself",
        application_lane="humble surrender that stops excusing hostile zeal once Christ exposes it for what it is",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "though his eyes were open, he could see nothing",
            "for three days he was without sight",
            "neither ate nor drank",
        ),
        pastoral_burden="helplessness after proud certainty is broken",
        theological_lane="divine interruption humbles proud certainty and leaves a person needy for mercy and direction",
        application_lane="patient dependence that accepts helplessness as a place where pride is dismantled and mercy is awaited",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "brother saul",
            "laying his hands on him",
            "something like scales fell from his eyes",
            "he got up and was baptized",
        ),
        pastoral_burden="restored sight and received fellowship after mercy arrives",
        theological_lane="the mercy of God restores, baptizes, and welcomes the humbled sinner into visible fellowship",
        application_lane="grateful reception of mercy that accepts both restoration and belonging instead of remaining isolated",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "lord, i have heard from many about this man",
            "go, for he is a chosen instrument of mine",
            "to bear my name before the gentiles and kings",
            "i will show him how much he must suffer",
        ),
        pastoral_burden="mercy chooses the least expected instrument and redefines his future",
        theological_lane="God's merciful choosing overturns human expectations and appoints even former enemies for costly service",
        application_lane="trust in God's surprising mercy that can repurpose the person you would have ruled out entirely",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "ananias",
            "here i am, lord",
            "the lord said to him in a vision",
            "he has seen in a vision a man named ananias",
        ),
        pastoral_burden="Ananias summoned into costly obedience before he understands the whole outcome",
        theological_lane="God often summons obedient servants before all the implications of mercy are visible to them",
        application_lane="ready obedience that answers the Lord before demanding a full explanation of how mercy will unfold",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "immediately he began to proclaim jesus in the synagogues",
            "all those hearing him continued to be amazed",
            "saul kept increasing in strength",
        ),
        pastoral_burden="new allegiance becoming unavoidable public witness",
        theological_lane="real conversion becomes public allegiance and cannot remain hidden when Christ has taken hold of a life",
        application_lane="public faithfulness that lets new allegiance become visible instead of protecting a private reputation",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "they were watching the gates day and night",
            "his disciples took him by night",
            "let him down through an opening in the wall",
        ),
        pastoral_burden="preserved through danger while early obedience remains costly",
        theological_lane="God preserves his servants through danger without removing the real cost of public allegiance",
        application_lane="steady obedience that accepts costly preservation instead of assuming faithfulness should be risk free",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "they were all afraid of him",
            "barnabas took hold of him",
            "the church throughout all judea and galilee and samaria enjoyed peace",
            "going on in the fear of the lord and in the comfort of the holy spirit",
        ),
        pastoral_burden="patient welcome and strengthening peace in the church",
        theological_lane="the church grows stronger through courageous mediation, holy fear, and the Spirit's comfort",
        application_lane="church life that practices discerning welcome and grows stronger through holy fear instead of suspicion or naïveté",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "aeneas",
            "jesus christ heals you",
            "all who lived at lydda and sharon saw him",
        ),
        pastoral_burden="healing mercy that turns whole communities toward the Lord",
        theological_lane="the Lord's healing power becomes public witness that redirects hearts toward him",
        application_lane="public gratitude that points beyond the gift itself to the Lord whose mercy has been seen",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "tabitha, arise",
            "she opened her eyes",
            "it became known all over joppa",
            "he was staying in joppa with a tanner named simon",
        ),
        pastoral_burden="resurrection mercy that leaves the servant ready for the next ordinary assignment",
        theological_lane="the Lord's life-giving mercy creates witness and then sends his servants back into ordinary readiness",
        application_lane="hopeful readiness that receives remarkable mercy without abandoning steady obedience in ordinary places",
    ),
    PassageCue(
        books=("acts",),
        contains_any=(
            "she was abounding with deeds of kindness and charity",
            "all the widows stood beside him, weeping",
            "showing all the tunics and garments",
        ),
        pastoral_burden="grief that remembers a life of embodied mercy",
        theological_lane="the fellowship of the church remembers mercy in concrete deeds and grieves the loss of faithful love",
        application_lane="present-tense kindness that leaves behind visible mercy worth remembering when grief comes",
    ),
)

LUKE_15_CUES: tuple[PassageCue, ...] = (
    PassageCue(
        books=("luke",),
        contains_any=(
            "tax collectors and sinners were all coming near",
            "this man receives sinners and eats with them",
        ),
        pastoral_burden="mercy that welcomes the very people religious pride keeps at a distance",
        theological_lane="the mercy of Christ receives sinners openly and exposes the coldness of self-righteous grumbling",
        application_lane="glad nearness to Christ that welcomes repentant sinners instead of guarding respectability through distance",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "what man among you, if he has a hundred sheep",
            "leaves the ninety-nine in the open pasture",
            "until he finds it",
            "he lays it on his shoulders, rejoicing",
        ),
        pastoral_burden="seeking mercy that refuses to leave the lost where they wandered",
        theological_lane="the shepherding mercy of God moves toward the lost with patient, joyful intention until they are found",
        application_lane="hopeful pursuit that reflects the shepherd's joy in recovering the lost rather than writing them off",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "rejoice with me, for i have found my sheep",
            "there will be more joy in heaven over one sinner who repents",
            "what woman, if she has ten silver coins",
            "she searches carefully until she finds it",
            "there is joy in the presence of the angels of god",
        ),
        pastoral_burden="heavenly joy over one repentant sinner",
        theological_lane="the joy of God and heaven over repentance dwarfs the stingy calculations of religious pride",
        application_lane="shared joy in repentance that celebrates grace instead of minimizing what heaven itself delights in",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "father, give me the share of the estate",
            "gathered everything together and went on a journey",
            "squandered his estate with loose living",
        ),
        pastoral_burden="rebellious desire that mistakes distance from the father for freedom",
        theological_lane="sinful independence spends the father's gifts while rejecting the father's presence",
        application_lane="honest repentance that stops calling self-ruled distance from God a form of freedom",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "a severe famine occurred",
            "he began to be impoverished",
            "he would have gladly filled his stomach with the pods",
            "no one was giving anything to him",
        ),
        pastoral_burden="the emptiness and humiliation that finally expose rebellion",
        theological_lane="the far country cannot sustain the sinner; ruin exposes the lie that rebellion can nourish the soul",
        application_lane="sobriety about sin's emptiness that stops romanticizing paths which finally leave people starving",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "he came to his senses",
            "i will get up and go to my father",
            "i have sinned against heaven and in your sight",
            "i am no longer worthy",
        ),
        pastoral_burden="repentance that comes to its senses and returns honestly",
        theological_lane="true repentance names sin plainly, abandons excuses, and turns back toward the father",
        application_lane="plainspoken repentance that rises and returns without bargaining away the truth about sin",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "while he was still a long way off",
            "his father saw him and felt compassion for him",
            "ran and embraced him and kissed him",
            "bring out the best robe",
        ),
        pastoral_burden="the father's compassionate welcome outruns the returning sinner",
        theological_lane="the father's compassion moves toward the repentant sinner with restoring love before merit can be claimed",
        application_lane="resting in the father's restoring mercy instead of trying to earn a place back through self-humbling performance",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "let us eat and celebrate",
            "this son of mine was dead and has come to life again",
            "he was lost and has been found",
        ),
        pastoral_burden="restoring joy that marks the homecoming of the lost",
        theological_lane="the father answers repentance with life, restoration, and celebratory joy over the found one",
        application_lane="grateful participation in the joy of restored fellowship instead of treating grace like a quiet technicality",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "his older son was in the field",
            "he became angry and was not willing to go in",
            "for so many years i have been serving you",
            "yet you have never given me a young goat",
        ),
        pastoral_burden="self-righteous resentment that refuses the joy of grace",
        theological_lane="religious pride can remain near the father's house while hating the father's mercy and joy",
        application_lane="repentance from resentful self-righteousness that measures grace like wages instead of receiving it as family mercy",
    ),
    PassageCue(
        books=("luke",),
        contains_any=(
            "my child, you have always been with me",
            "all that is mine is yours",
            "we had to celebrate and rejoice",
        ),
        pastoral_burden="the father's appeal to share his joy instead of standing outside in pride",
        theological_lane="the father's generosity invites resentful children to come inside and share the joy of mercy",
        application_lane="coming inside the joy of grace by receiving the father's generosity instead of standing outside with offended pride",
    ),
)


JOHN_10_CUES: tuple[PassageCue, ...] = (
    PassageCue(
        books=("john",),
        contains_any=(
            "know his voice",
            "they know his voice",
            "stranger they simply will not follow",
            "will not follow a stranger",
            "voice of strangers",
        ),
        pastoral_burden="trustful following that knows the shepherd's voice and refuses the stranger's",
        theological_lane="the sheep's security rests on knowing the shepherd's voice and fleeing every voice that is not his",
        application_lane="attentive listening that follows the shepherd's voice and refuses every competing call that is not his",
    ),
    PassageCue(
        books=("john",),
        contains_any=(
            "i am the good shepherd",
            "good shepherd lays down his life",
            "good shepherd lays down",
            "hired hand",
            "hired hand flees",
        ),
        pastoral_burden="the good shepherd's self-giving life laid down for the sheep",
        theological_lane="the Good Shepherd's love is proved not by noble feeling but by life laid down for the sheep the hired hand abandons",
        application_lane="trusting surrender under the Good Shepherd who lays down his life where the hired hand flees",
    ),
    PassageCue(
        books=("john",),
        contains_any=(
            "lay it down on my own initiative",
            "i have authority to lay it down",
            "authority to lay it down",
            "commandment i received from my father",
            "this commandment i received",
        ),
        pastoral_burden="the shepherd's voluntary authority over his own life given in obedience to the Father",
        theological_lane="the Son lays down his life freely by the Father's commandment, making his death an act of sovereign obedience not defeated helplessness",
        application_lane="willing obedience that entrusts life and death to the Father's commandment, following the shepherd who laid down his own",
    ),
    PassageCue(
        books=("john",),
        contains_any=(
            "you do not believe because you are not of my sheep",
            "not of my sheep",
            "works that i do in my father's name",
            "testify of me",
            "these testify of me",
        ),
        pastoral_burden="belonging to Christ's sheep proved by believing his testimony",
        theological_lane="unbelief is not a knowledge problem but a belonging problem — those who are his sheep hear and follow; those who are not, refuse",
        application_lane="faith that receives Christ's testimony from the Father and proves belonging to his sheep by believing his works",
    ),
    PassageCue(
        books=("john",),
        contains_any=(
            "make yourself out to be god",
            "make yourself god",
            "many good works from the father",
            "for which of them are you stoning",
            "stoning me",
        ),
        pastoral_burden="Christ's divine works from the Father confronting hostile unbelief",
        theological_lane="Christ's works from the Father bear public witness to his identity even when that witness draws hostility rather than faith",
        application_lane="bold witness that presents Christ's works from the Father without softening his divine claims to avoid rejection",
    ),
    PassageCue(
        books=("john",),
        contains_any=(
            "eluded their grasp",
            "beyond the jordan",
            "seeking again to seize him",
            "they were seeking again to seize",
            "no one will snatch them out of my hand",
            "snatch them out of my hand",
            "no one is able to snatch",
        ),
        pastoral_burden="Christ's sovereign life that cannot be seized by those who reject him",
        theological_lane="the same authority that gives eternal life to his sheep sovereignly eludes every human attempt to seize or silence the shepherd",
        application_lane="steadfast trust in the Christ who goes beyond the Jordan rather than surrendering to those who seek to seize him, sovereign in every movement",
    ),
)


ROMANS_5_CUES: tuple[PassageCue, ...] = (
    PassageCue(
        books=("romans",),
        contains_any=(
            "having been justified by faith",
            "justified by faith we have peace",
            "we have peace with god",
            "access by faith into this grace",
            "we exult in hope of the glory",
        ),
        pastoral_burden="peace with God received through justification by faith alone",
        theological_lane="justification by faith alone gives the sinner standing, peace, and access to grace that no human effort could earn or sustain",
        application_lane="joyful hope in the glory of God that flows from peace with him, received by faith alone and not by effort added to what Christ finished",
    ),
    PassageCue(
        books=("romans",),
        contains_any=(
            "hope does not disappoint",
            "hope does not put us to shame",
            "while we were still helpless",
            "at the right time christ died for the ungodly",
            "christ died for the ungodly",
        ),
        pastoral_burden="hope that holds firm because Christ died for the helpless before they deserved it",
        theological_lane="hope rooted in suffering does not shame the believer because God's love was proved by Christ dying for the ungodly before any merit existed",
        application_lane="hope-filled endurance that rests on Christ who died for the helpless before they deserved it, not on strength that suffering tests",
    ),
    PassageCue(
        books=("romans",),
        contains_any=(
            "while we were enemies we were reconciled",
            "we were reconciled to god",
            "saved by his life",
            "we also exult in god",
            "through whom we have now received the reconciliation",
        ),
        pastoral_burden="reconciliation with God received while we were still enemies",
        theological_lane="God reconciled his enemies to himself through Christ's death and keeps them by his risen life, making boasting in God the proper response",
        application_lane="bold rejoicing in God through Christ, who reconciled enemies by his death and saves them by his life without waiting for them to become worthy",
    ),
    PassageCue(
        books=("romans",),
        contains_any=(
            "sin came into the world through one man",
            "death spread to all men",
            "all sinned",
            "death reigned from adam",
            "sin is not imputed when there is no law",
        ),
        pastoral_burden="the solidarity of death and sin inherited through Adam that exposes every person's need",
        theological_lane="sin and death entered through one man and spread to all, demonstrating that humanity's problem requires a solution from outside itself",
        application_lane="sober acknowledgment that death and sin came through Adam's trespass and spread to all, leaving every person in need of another man's obedience",
    ),
    PassageCue(
        books=("romans",),
        contains_any=(
            "the free gift is not like the transgression",
            "gift of righteousness",
            "reign in life through the one",
            "those who receive the abundance of grace",
            "much more those who receive the abundance",
        ),
        pastoral_burden="the free gift of righteousness that far exceeds the reach of the transgression",
        theological_lane="where the transgression brought condemnation, the free gift of grace and righteousness brings justification and life that overflows beyond the damage",
        application_lane="joyful reception of the free gift of righteousness that far exceeds the transgression, given by grace not earned by those who receive it",
    ),
    PassageCue(
        books=("romans",),
        contains_any=(
            "through the one man's obedience the many will be made righteous",
            "one man's obedience",
            "where sin increased grace abounded all the more",
            "grace abounded all the more",
            "so that as sin reigned in death",
            "grace would reign through righteousness",
        ),
        pastoral_burden="grace that abounded more than sin through the obedience of the one man",
        theological_lane="where Adam's disobedience brought condemnation to many, Christ's obedience brings righteousness and life, with grace abounding beyond every measure of sin",
        application_lane="humble wonder at grace that abounded beyond sin's increase, grounded entirely in Christ's obedience rather than the obedience of those who receive it",
    ),
)


PASSAGE_CUES: tuple[PassageCue, ...] = (
    LUKE_5_6_CUES
    + LUKE_15_CUES
    + COLOSSIANS_3_4_CUES
    + EXODUS_19_20_CUES
    + PROVERBS_1_2_CUES
    + ACTS_9_CUES
    + JOHN_10_CUES
    + ROMANS_5_CUES
)


def _book_matches(reference: str, cue: PassageCue) -> bool:
    ref = (reference or "").strip().lower()
    return any(ref.startswith(book) for book in cue.books)


def resolve_passage_cue(
    *,
    reference: str,
    focus_clause: str,
    scripture_text: str,
) -> PassageCue | None:
    haystack = f"{focus_clause} {scripture_text}".lower()
    for cue in PASSAGE_CUES:
        if not _book_matches(reference, cue):
            continue
        if any(term in haystack for term in cue.contains_any):
            return cue
    return None
