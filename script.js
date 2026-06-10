// List of Pyxel games
// TODO: fill demoUrl after publishing each demo to pyxelstudio.net
// (paste a demo file at https://www.pyxelstudio.net, save, copy the URL here)
var games = [
    {
        title: 'Color Mycelium',
        description: 'Branching hyphae paint slow rainbow threads. Click to plant spores, C cycles palettes, F toggles fade.',
        image: '/demos/color_mycelium.PNG',
        demoUrl: 'https://www.pyxelstudio.net/e8zt3afs',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/color_mycelium.py',
    },
    {
        title: 'Mycelium Garden',
        description: 'Hyphae forage for nutrients, fatten up, and fruit into mushrooms that puff spores. Click to feed the network.',
        image: '/demos/mycelium_garden.PNG',
        demoUrl: 'https://www.pyxelstudio.net/h7kq4gws',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/mycelium_garden.py',
    },
    {
        title: 'Powder Box',
        description: 'A falling-sand sandbox: sand, water, walls, plants, and fire. Paint with the mouse, keys 1-5 pick elements.',
        image: '/demos/powder_box.PNG',
        demoUrl: '#',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/powder_box.py',
    },
    {
        title: 'Terrarium',
        description: 'A glass jar of tiny leaf-headed pips that trot, hop, and float. Drop berries, watch eggs hatch, fireflies at night.',
        image: '/demos/terrarium.PNG',
        demoUrl: '#',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/terrarium.py',
    },
    {
        title: 'Physarum',
        description: 'A slime mold of 320 blind agents builds veiny transport networks out of nothing. Hold click to drop food scent.',
        image: '/demos/physarum.PNG',
        demoUrl: '#',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/physarum.py',
    },
    {
        title: 'Hex Bloom',
        description: 'Snowflake crystals bloom on a hexagonal grid via the Ulam-Warburton rule. Click to seed, U swaps flake/coral.',
        image: '/demos/hex_bloom.PNG',
        demoUrl: '#',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/hex_bloom.py',
    },
    {
        title: 'Oculus Garden',
        description: 'A moonlit bed of eye-stalks that sway, track your cursor, and get shy if you stare. Click soil to grow more.',
        image: '/demos/oculus_garden.PNG',
        demoUrl: '#',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/oculus_garden.py',
    },
    {
        title: 'Lava Lamp',
        description: 'Six metaball blobs of goo melt into each other, kept circulating by heat. Click to poke, Z/X change blob count.',
        image: '/demos/lava_lamp.PNG',
        demoUrl: '#',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/lava_lamp.py',
    },
    {
        title: 'Koi Pond',
        description: 'Four koi drift as flexing chains of circles, nosing toward ripples. Tap the water and watch them come.',
        image: '/demos/koi_pond.PNG',
        demoUrl: '#',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/koi_pond.py',
    },
];

// Get the game list container
var gameList = document.getElementById('game-list');

// Populate the game list
games.forEach(function(game) {
    var gameCard = document.createElement('div');
    gameCard.className = 'game-card';

    gameCard.innerHTML = `
        <h2>${game.title}</h2>
        <img src="${game.image}" alt="${game.title}">
        <p>${game.description}</p>
        <a href="${game.demoUrl}" target="_blank">Demo</a> | 
        <a href="${game.codeUrl}" target="_blank">Code</a>
    `;

    gameList.appendChild(gameCard);
});
