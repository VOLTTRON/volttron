'use strict';

var webpack = require('webpack');
var path = require('path');
const ExtractTextPlugin = require('extract-text-webpack-plugin')

// to remove previous files
var CleanWebpackPlugin = require('clean-webpack-plugin');

// inserts js and css into html file
var HtmlWebpackPlugin = require('html-webpack-plugin');

// enforce same case as file system
var CaseSensitivePathsPlugin = require('case-sensitive-paths-webpack-plugin');

var argv = require('yargs').argv;
var url = require('url');

// --p or --optimize-minimize
const IS_PRODUCTION = argv.p || argv['optimize-minimize'];

const BUILD_PATH = path.join(__dirname, './volttroncentral/webroot/vc');

const HTML_FILE_NAME = 'index.html';

// webpack will hash in square brackets for production builds
var doHash = IS_PRODUCTION ? '.[hash]' : '';

module.exports = {
    context: path.join(__dirname, '/ui-src'),
    entry: {
        app: './js/app.jsx'
    },
    output: {
        path: BUILD_PATH,
        publicPath: './',
        filename: 'js/[name]-[hash].js',
    },
    resolve: {
        //Allow locating dependancies relative to the src directory and then the js directory.
        // no need for .. hell
        root: [
            __dirname
        ],
        fallback: [
            __dirname,
            path.join(__dirname, '/ui-src'),
            path.join(__dirname, '/ui-src/js'),
        ],
        extensions: [
            '', 
            '.js', 
            '.jsx'
        ],
        alias: {
            symbol: 'es6-symbol',
        },
    },
    module: {
        preLoaders: [
            {
                test: /\.jsx?$/,
                exclude: [
                    /node_modules/
                ],
                loaders: [
                    'eslint'
                ],
            },
        ],
        loaders: [
            {
                test: /\.(js|jsx)$/,
                loaders: ['babel'],
                include: path.join(__dirname, 'ui-src')
            },
            {
                test: /\.css$/,
                loader: ExtractTextPlugin.extract("style-loader", "css-loader"),
                include: path.join(__dirname, 'ui-src')
            },
            {
                test: /\.css$/,
                loaders: ['style', 'css?importLoaders=1'],
                include: path.join(__dirname, 'node_modules')
            },
            { 
                test: /\.json$/, 
                loader: 'json-loader' 
            },
            // png/jpg will be in bundle under 8k, otherwise file with path
            { 
                test: /\.(png|jpg)$/, 
                loader: 'url-loader?limit=8192' 
            },
            // fonts 10k or less in bundle, fallback fonts always in files
            { 
                test: /\.woff(2)?(\?v=[0-9]\.[0-9]\.[0-9])?$/, 
                loader: 'url-loader?limit=10000&name=fonts/[name]-[ext]' 
            },
            { 
                test: /\.(ttf|eot|svg)(\?v=[0-9]\.[0-9]\.[0-9])?$/, 
                loader: 'file-loader?name=fonts/[name]-[ext]' 
            },
        ],
    },
    node: {fs: "empty"},
    plugins: [
        // inserts js and css into html file
        new HtmlWebpackPlugin({
            filename: HTML_FILE_NAME,
            template: HTML_FILE_NAME
        }),
        new CaseSensitivePathsPlugin(),
        new CleanWebpackPlugin([
            BUILD_PATH + "/js", 
            BUILD_PATH + "/css", 
            BUILD_PATH + "/fonts"
        ]),
        
        new ExtractTextPlugin("css/[name]-[hash].css")

    ],
    devServer: {
        inline: true,
        port: 65410,
        proxy: {
            '*': 'http://localhost:8080'
        },
        historyApiFallback: true,
    },
};

if (IS_PRODUCTION) {
    module.exports.plugins.push(new webpack.DefinePlugin({ 'process.env': { NODE_ENV: '"production"' } }));
}