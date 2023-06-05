// List of Pyxel games
var games = [
    {
        title: 'Color Mycelium',
        description: 'A color mycelium demo',
        image: 'path/to/color_mycelium.png',
        demoUrl: 'https://www.pyxelstudio.net/e8zt3afs',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/color_mycelium.py',
    },
    {
        title: 'Mycelium 1',
        description: 'Another mycelium demo',
        image: 'path/to/mycelium_1.png',
        demoUrl: 'https://www.pyxelstudio.net/h7kq4gws',
        codeUrl: 'https://github.com/alexkorol/pyxel-arcade/blob/master/demos/mycelium_1.py',
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