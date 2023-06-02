// List of Pyxel games
var games = [
    {
        title: 'Hello Pyxel',
        description: 'Simplest application',
        image: 'path/to/hello_pyxel.png',
        demoUrl: 'path/to/hello_pyxel/demo',
        codeUrl: 'path/to/hello_pyxel/code',
    },
    // Add more game objects here...
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
